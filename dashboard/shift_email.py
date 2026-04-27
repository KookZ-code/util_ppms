"""Shift-end email summary — query data, build HTML, send via SMTP."""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

import pandas as pd

log = logging.getLogger(__name__)

# Area groups — one email covers multiple areas
AREA_GROUPS = {
    'EOL':  ['MARK', 'TF', 'ISO', 'FS'],
    'BSDA': ['BG', 'SAW', 'DA'],
}
AREA_GROUP_NAMES = {
    'EOL':  'End of Line',
    'BSDA': 'BG · SAW · DA',
}


def _get_smtp_config():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
    return {
        'host': os.getenv('SMTP_HOST', ''),
        'port': int(os.getenv('SMTP_PORT', '587')),
        'user': os.getenv('SMTP_USER', ''),
        'password': os.getenv('SMTP_PASSWORD', ''),
        'from_addr': os.getenv('SMTP_FROM', ''),
        'use_tls': os.getenv('SMTP_TLS', '1') == '1',
    }


def _get_recipients():
    """Parse SHIFT_EMAIL_RECIPIENTS from .env.
    Format: DA:email1@x.com,SAW:email2@x.com,ALL:manager@x.com
    ALL = receives every area's report.
    Returns: {area: [emails]}
    """
    raw = os.getenv('SHIFT_EMAIL_RECIPIENTS', '')
    recipients = {}
    all_emails = []
    for part in raw.split(','):
        part = part.strip()
        if ':' in part:
            area, email = part.split(':', 1)
            area = area.strip()
            email = email.strip()
            if not email:
                continue  # skip empty emails
            if area.upper() == 'ALL':
                all_emails.append(email)
            else:
                recipients.setdefault(area, []).append(email)
    # Areas covered by groups (don't send separately)
    grouped_areas = set()
    for grp, subs in AREA_GROUPS.items():
        if grp in recipients:
            grouped_areas.update(subs)

    # Append ALL emails to every area (except grouped sub-areas)
    if all_emails:
        for area in list(recipients.keys()):
            for e in all_emails:
                if e not in recipients[area]:
                    recipients[area].append(e)
        from config import MACHINE_AREAS
        for area in MACHINE_AREAS:
            if area not in recipients and area not in grouped_areas:
                recipients[area] = list(all_emails)
    return recipients


def _get_shift_range(shift_name):
    """Get start/end datetime for the shift that just ended."""
    now = datetime.now()
    if shift_name == 'Day':
        # Day shift: 07:00 today → 18:59 today
        start = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end = now.replace(hour=18, minute=59, second=59, microsecond=0)
    else:
        # Night shift: 19:00 yesterday → 06:59 today
        start = (now - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        end = now.replace(hour=6, minute=59, second=59, microsecond=0)
    return start, end


def _query_shift_data(area, shift_name, start, end):
    """Query downtime events for a specific area and shift time range."""
    from db import query_df
    from config import VIEW_NAME

    # Events in this shift
    events_df = query_df(f"""
        SELECT code_machine AS machine_id, id_operation AS area,
               job_type, des_job AS symptom, cause, [action],
               datex AS event_time,
               ISNULL(by_perform, by_ack) AS tech,
               ISNULL(Waiting_time, 0) AS wait_min,
               DATEDIFF(MINUTE, date_ack, date_close) AS repair_min,
               [Package Type] AS package_type, [lot_no], [mpc] AS die_mask
        FROM {VIEW_NAME}
        WHERE id_operation = :area
          AND datex >= :start_dt AND datex <= :end_dt
          AND date_ack IS NOT NULL AND date_close > date_ack
        ORDER BY datex DESC
    """, {'area': area, 'start_dt': start, 'end_dt': end})

    # Unclosed jobs
    if area == 'DA':
        # DA: count jobs with action = "waiting for repair to continue"
        unclosed_df = query_df(f"""
            SELECT code_machine, job_type, des_job, [action]
            FROM {VIEW_NAME}
            WHERE id_operation = :area
              AND datex >= :start_dt AND datex <= :end_dt
              AND date_ack IS NOT NULL AND date_close > date_ack
              AND LOWER([action]) = 'waiting for repair to continue'
        """, {'area': area, 'start_dt': start, 'end_dt': end})
    else:
        unclosed_df = query_df("""
            SELECT code_machine, job_type, des_job
            FROM dbo.job_list
            WHERE id_operation = :area
              AND date_close IS NULL
              AND datex >= :start_dt
        """, {'area': area, 'start_dt': start})

    # Yesterday's utilization for comparison
    yesterday_start = start - timedelta(days=1)
    yesterday_end = end - timedelta(days=1)
    prev_df = query_df(f"""
        SELECT job_type,
               SUM(DATEDIFF(MINUTE, date_ack, date_close)) AS total_min,
               SUM(ISNULL(Waiting_time, 0)) AS wait_min
        FROM {VIEW_NAME}
        WHERE id_operation = :area
          AND datex >= :start_dt AND datex <= :end_dt
          AND date_ack IS NOT NULL AND date_close > date_ack
        GROUP BY job_type
    """, {'area': area, 'start_dt': yesterday_start, 'end_dt': yesterday_end})

    # Merge Oracle data for ISO/FS areas
    try:
        from config import ORA_ENABLED
        from oracle_db import ORACLE_AREA_MAP
        if ORA_ENABLED and area in ORACLE_AREA_MAP:
            from oracle_db import fetch_oracle_data, _store, _ensure_loaded
            import time as _t
            # Ensure Oracle data is loaded (wait up to 45s for background load)
            _ensure_loaded()
            for _ in range(45):
                if _store['df'] is not None:
                    break
                _t.sleep(1)
            shift_code = 'DAY' if shift_name == 'Day' else 'NIGHT'
            ora = fetch_oracle_data(
                start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'),
                areas=[area], shift=shift_code)
            if ora is not None:
                # Oracle datex is DATE (midnight) — use date_ack for actual time
                ora['event_time'] = pd.to_datetime(ora['date_ack'], errors='coerce')
                # Filter: events within shift time range
                ora = ora[(ora['event_time'] >= start) & (ora['event_time'] <= end)]
                # Fallback: if date_ack has no time, filter by date only
                if ora.empty:
                    ora_retry = fetch_oracle_data(
                        start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'),
                        areas=[area], shift=shift_code)
                    if ora_retry is not None:
                        ora = ora_retry
                        ora['event_time'] = pd.to_datetime(ora['datex'], errors='coerce')
                if not ora.empty:
                    ora_ev = ora.rename(columns={
                        'badge': 'tech', 'symptom': 'symptom', 'cause': 'cause',
                    })[['machine_id', 'area', 'job_type', 'symptom', 'cause',
                        'event_time', 'tech', 'wait_min', 'repair_min']].copy()
                    ora_ev['action'] = ora_ev['cause']  # Oracle has no separate action
                    ora_ev['wait_min'] = pd.to_numeric(ora_ev['wait_min'], errors='coerce').fillna(0).astype(int)
                    ora_ev['repair_min'] = pd.to_numeric(ora_ev['repair_min'], errors='coerce').fillna(0).astype(int)
                    events_df = pd.concat([events_df, ora_ev], ignore_index=True)
                    events_df = events_df.sort_values('event_time', ascending=False)
    except Exception as e:
        log.warning(f"Oracle merge for {area} email failed: {e}")

    return events_df, unclosed_df, prev_df


def _calc_utilization(events_df, machine_count, hours):
    """Calculate utilization/downtime/lost %. Returns (util, down, lost)."""
    if machine_count <= 0:
        return 0.0, 0.0, 0.0
    avail = machine_count * hours * 60
    if avail <= 0:
        return 0.0, 0.0, 0.0
    down_types = ('M/C DOWN',)
    pm_types = ('PM',)
    lost_types = ('SETUP', 'SETUP BY OPERATOR', 'CONVERT', 'FACILITY DOWN',
                  'ENGINEERING DOWN', 'CLEAN MOLD', 'CHANGE CAP')
    down = events_df[events_df['job_type'].isin(down_types)]['repair_min'].sum()
    pm = events_df[events_df['job_type'].isin(pm_types)]['repair_min'].sum()
    lost = (events_df[events_df['job_type'].isin(lost_types)]['repair_min'].sum()
            + events_df['wait_min'].sum())
    down_pct = round(down / avail * 100, 2)
    lost_pct = round(lost / avail * 100, 2)
    util_pct = round(max(0, 100 - down_pct - round(pm / avail * 100, 2) - lost_pct), 2)
    return util_pct, down_pct, lost_pct


def _build_html_email(area, area_name, shift_name, date_str, start, end,
                      events_df, unclosed_df, util_pct, down_pct, lost_pct,
                      prev_util_pct):
    """Build professional HTML email."""
    # Ensure numeric columns
    events_df['repair_min'] = pd.to_numeric(events_df['repair_min'], errors='coerce').fillna(0)
    events_df['wait_min'] = pd.to_numeric(events_df['wait_min'], errors='coerce').fillna(0)

    # Filter: M/C DOWN + SETUP (Tech) + CONVERT — exclude SETUP BY OPERATOR
    relevant = events_df[events_df['job_type'].isin(['M/C DOWN', 'SETUP', 'CONVERT'])].copy()

    mc_down = relevant[relevant['job_type'] == 'M/C DOWN']
    setup = relevant[relevant['job_type'] == 'SETUP']
    convert = relevant[relevant['job_type'] == 'CONVERT']
    mc_events = len(mc_down)
    mc_hrs = round(mc_down['repair_min'].sum() / 60, 1) if not mc_down.empty else 0
    setup_events = len(setup)
    setup_hrs = round(setup['repair_min'].sum() / 60, 1) if not setup.empty else 0
    convert_events = len(convert)
    convert_hrs = round(convert['repair_min'].sum() / 60, 1) if not convert.empty else 0
    unclosed = len(unclosed_df)

    # KPIs based on relevant events only
    mttr = int(relevant['repair_min'].mean()) if not relevant.empty else 0
    mttw = int(relevant['wait_min'].mean()) if not relevant.empty else 0
    hours = 12
    mc_count = events_df['machine_id'].nunique() if not events_df.empty else 1
    avail_min = mc_count * hours * 60
    mtba = round(avail_min / 60 / max(mc_events, 1), 1)  # MTBA based on M/C DOWN only

    # Trend
    delta = round(util_pct - prev_util_pct, 1) if prev_util_pct else 0
    trend_arrow = "▲" if delta > 0 else "▼" if delta < 0 else "—"
    trend_color = "#2E9E4F" if delta > 0 else "#CC0000" if delta < 0 else "#8A96A8"
    trend_text = f"{trend_arrow} {'+' if delta > 0 else ''}{delta}% vs yesterday"

    # Top 3 machines
    top3 = ""
    if not mc_down.empty:
        m_agg = mc_down.groupby('machine_id').agg(
            events=('repair_min', 'count'),
            down_hrs=('repair_min', lambda x: round(x.sum() / 60, 1)),
            top_symptom=('symptom', lambda x: x.mode().iloc[0] if not x.mode().empty else '—'),
        ).reset_index().nlargest(3, 'down_hrs')
        for i, (_, r) in enumerate(m_agg.iterrows(), 1):
            top3 += f"""
            <tr>
                <td style="padding:6px 10px;color:#4A5568;font-weight:600">{i}</td>
                <td style="padding:6px 10px;font-weight:600">{r['machine_id']}</td>
                <td style="padding:6px 10px;text-align:center">{r['events']}</td>
                <td style="padding:6px 10px;text-align:center;color:#CC0000;font-weight:600">{r['down_hrs']}h</td>
                <td style="padding:6px 10px;color:#4A5568">{r['top_symptom']}</td>
            </tr>"""

    # Event detail rows — only top 3 machines
    top3_machines = []
    if not mc_down.empty:
        top3_machines = (mc_down.groupby('machine_id')['repair_min'].sum()
                         .nlargest(3).index.tolist())
    detail_events = relevant[relevant['machine_id'].isin(top3_machines)] if top3_machines else relevant.head(0)
    n_detail = len(detail_events)

    event_rows = ""
    for _, r in detail_events.iterrows():
        t = pd.to_datetime(r['event_time']).strftime('%H:%M') if pd.notna(r['event_time']) else ''
        jt_color = "#CC0000" if r['job_type'] == 'M/C DOWN' else "#1D9CE4"
        event_rows += f"""
        <tr style="border-bottom:1px solid #EEF0F4">
            <td style="padding:5px 8px;font-size:12px">{t}</td>
            <td style="padding:5px 8px;font-size:12px;font-weight:600">{r['machine_id']}</td>
            <td style="padding:5px 8px;font-size:12px;color:{jt_color};font-weight:600">{r['job_type']}</td>
            <td style="padding:5px 8px;font-size:12px">{r.get('symptom','')}</td>
            <td style="padding:5px 8px;font-size:12px;color:#6B3FA0">{r.get('action','')}</td>
            <td style="padding:5px 8px;font-size:12px">{r.get('tech','')}</td>
            <td style="padding:5px 8px;font-size:12px;text-align:right;color:#FD7F20">{int(r['wait_min'])}m</td>
            <td style="padding:5px 8px;font-size:12px;text-align:right;color:#CC0000">{int(r['repair_min'])}m</td>
            <td style="padding:5px 8px;font-size:11px;color:#4A5568">{r.get('package_type','')}</td>
            <td style="padding:5px 8px;font-size:11px;color:#4A5568">{r.get('lot_no','')}</td>
            <td style="padding:5px 8px;font-size:11px;color:#4A5568">{r.get('die_mask','')}</td>
        </tr>"""

    shift_label = "Day Shift" if shift_name == "Day" else "Night Shift"
    time_range = f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"

    html = f"""
    <div style="font-family:'IBM Plex Sans',Calibri,sans-serif;max-width:800px;margin:0 auto;background:#fff">

        <!-- Header -->
        <div style="background:#0E3689;padding:16px 24px;border-radius:10px 10px 0 0">
            <div style="color:#FFD53A;font-size:12px;font-weight:600;letter-spacing:0.5px">SHIFT SUMMARY</div>
            <div style="color:#fff;font-size:20px;font-weight:700;font-family:'DM Sans',sans-serif;margin-top:4px">
                {area} — {area_name}
            </div>
            <div style="color:rgba(255,255,255,0.7);font-size:13px;margin-top:2px">
                {shift_label} · {date_str} · {time_range}
            </div>
        </div>

        <!-- Utilization + Downtime + Lost Time -->
        <div style="background:#F0F2F5;padding:16px 24px;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap">
            <span style="font-size:32px;font-weight:700;color:#0E3689">{util_pct}%</span>
            <span style="font-size:14px;color:#4A5568">Utilization</span>
            <span style="font-size:13px;color:{trend_color};font-weight:600">{trend_text}</span>
            <span style="font-size:14px;color:#8A96A8;margin-left:8px">|</span>
            <span style="font-size:14px;color:#CC0000;font-weight:700">{down_pct}%</span>
            <span style="font-size:12px;color:#4A5568">Downtime</span>
            <span style="font-size:14px;color:#8A96A8">|</span>
            <span style="font-size:14px;color:#FD7F20;font-weight:700">{lost_pct}%</span>
            <span style="font-size:12px;color:#4A5568">Lost Time</span>
        </div>

        <!-- KPI Box -->
        <div style="padding:16px 24px">
            <table style="width:100%;border-collapse:collapse;background:#FAFBFC;border-radius:8px;overflow:hidden">
                <tr>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4">
                        <span style="color:#CC0000;font-weight:700">M/C DOWN</span>
                    </td>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4;text-align:right">
                        <b>{mc_events}</b> events · <b>{mc_hrs}</b> hrs
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4">
                        <span style="color:#1D9CE4;font-weight:700">SETUP (Tech)</span>
                    </td>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4;text-align:right">
                        <b>{setup_events}</b> events · <b>{setup_hrs}</b> hrs
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4">
                        <span style="color:#FFD53A;font-weight:700">CONVERT</span>
                    </td>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4;text-align:right">
                        <b>{convert_events}</b> events · <b>{convert_hrs}</b> hrs
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4">
                        <span style="color:#FD7F20;font-weight:700">Unclosed Jobs</span>
                    </td>
                    <td style="padding:12px 16px;border-bottom:1px solid #EEF0F4;text-align:right">
                        <b>{unclosed}</b> still on process
                    </td>
                </tr>
                <tr>
                    <td colspan="2" style="padding:12px 16px">
                        <span style="color:#4A5568">MTTR: <b>{mttr}</b> min</span>
                        <span style="color:#4A5568;margin-left:20px">MTTW: <b>{mttw}</b> min</span>
                        <span style="color:#4A5568;margin-left:20px">MTBA: <b>{mtba}</b> hrs</span>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Top 3 Machines -->
        <div style="padding:0 24px 16px">
            <div style="font-size:14px;font-weight:700;color:#1A1F2E;margin-bottom:8px;
                        font-family:'DM Sans',sans-serif;border-bottom:2px solid #CC0000;
                        padding-bottom:6px">
                Top 3 Machines
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <tr style="background:#EDF2FF">
                    <th style="padding:8px 10px;text-align:left;color:#0E3689;font-size:11px">#</th>
                    <th style="padding:8px 10px;text-align:left;color:#0E3689;font-size:11px">Machine</th>
                    <th style="padding:8px 10px;text-align:center;color:#0E3689;font-size:11px">Events</th>
                    <th style="padding:8px 10px;text-align:center;color:#0E3689;font-size:11px">Down Hrs</th>
                    <th style="padding:8px 10px;text-align:left;color:#0E3689;font-size:11px">Top Symptom</th>
                </tr>
                {top3 if top3 else '<tr><td colspan="5" style="padding:10px;color:#8A96A8">No M/C DOWN events</td></tr>'}
            </table>
        </div>

        <!-- Event Detail -->
        <div style="padding:0 24px 16px">
            <div style="font-size:14px;font-weight:700;color:#1A1F2E;margin-bottom:8px;
                        font-family:'DM Sans',sans-serif;border-bottom:2px solid #0E3689;
                        padding-bottom:6px">
                Event Detail — Top 3 Machines ({n_detail} events)
            </div>
            <table style="width:100%;border-collapse:collapse;font-size:12px">
                <tr style="background:#EDF2FF">
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Time</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Machine</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Type</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Symptom</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Action</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Tech</th>
                    <th style="padding:6px 8px;text-align:right;color:#0E3689;font-size:11px">Wait</th>
                    <th style="padding:6px 8px;text-align:right;color:#0E3689;font-size:11px">Repair</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Package</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Lot No.</th>
                    <th style="padding:6px 8px;text-align:left;color:#0E3689;font-size:11px">Die Mask</th>
                </tr>
                {event_rows if event_rows else '<tr><td colspan="11" style="padding:10px;color:#8A96A8">No events for top 3 machines</td></tr>'}
            </table>
        </div>

        <!-- Footer -->
        <div style="background:#F0F2F5;padding:12px 24px;border-radius:0 0 10px 10px;
                     text-align:center;font-size:12px;color:#8A96A8">
            <a href="http://10.50.21.96:8050/downtime" style="color:#0E3689;text-decoration:none;font-weight:600">
                View Full Dashboard
            </a>
            <br>
            <span style="font-size:11px">Auto-generated · Microchip Technology · Proprietary and Confidential</span>
        </div>
    </div>
    """
    return html


def send_shift_summary(shift_name):
    """Main function: query all areas, build emails, send to supervisors."""
    enabled = os.getenv('SHIFT_EMAIL_ENABLED', '0') == '1'
    if not enabled:
        log.info("Shift email disabled (SHIFT_EMAIL_ENABLED=0)")
        return

    smtp = _get_smtp_config()
    recipients = _get_recipients()
    if not recipients:
        log.warning("No SHIFT_EMAIL_RECIPIENTS configured")
        return

    start, end = _get_shift_range(shift_name)
    date_str = start.strftime('%B %d, %Y')

    # Area name mapping
    area_names = {
        'BG': 'Back Grind', 'DA': 'Die Attach', 'SAW': 'SAW',
        'WB': 'Wire Bond', 'MOLD': 'Mold', 'PLATE': 'Plating',
        'MARK': 'Marking', 'TF': 'Trim Form', 'ISO': 'Isolate',
        'FS': 'Form Singulation', 'SAW_QFN': 'SAW QFN',
    }

    for area, emails in recipients.items():
        try:
            if area in AREA_GROUPS:
                # Group area (e.g. EOL) — combine multiple sub-areas into one email
                sub_areas = AREA_GROUPS[area]
                group_name = AREA_GROUP_NAMES.get(area, area)
                sections_html = []
                for sub in sub_areas:
                    ev, unc, prev = _query_shift_data(sub, shift_name, start, end)
                    mc = ev['machine_id'].nunique() if not ev.empty else 1
                    u, d, l = _calc_utilization(ev, mc, 12)
                    pu = None
                    if not prev.empty:
                        pu, _, _ = _calc_utilization(
                            pd.DataFrame({'job_type': prev['job_type'],
                                          'repair_min': prev['total_min'],
                                          'wait_min': prev['wait_min'],
                                          'machine_id': ['x'] * len(prev)}),
                            mc, 12)
                    sub_name = area_names.get(sub, sub)
                    sections_html.append(
                        _build_html_email(sub, sub_name, shift_name, date_str,
                                          start, end, ev, unc, u, d, l, pu))
                # Combine all sections with divider
                divider = '<div style="border-top:3px solid #0E3689;margin:24px 0"></div>'
                html_body = divider.join(sections_html)
                subject = f"[{area}] {shift_name} Shift Summary — {group_name} — {date_str}"
                _send_email(smtp, emails, subject, html_body)
                log.info(f"Sent {shift_name} group email [{area}] ({sub_areas}) to {emails}")
            else:
                # Single area
                events_df, unclosed_df, prev_df = _query_shift_data(area, shift_name, start, end)
                mc_count = events_df['machine_id'].nunique() if not events_df.empty else 1
                util_pct, down_pct, lost_pct = _calc_utilization(events_df, mc_count, 12)
                prev_util = None
                if not prev_df.empty:
                    prev_util, _, _ = _calc_utilization(
                        pd.DataFrame({'job_type': prev_df['job_type'],
                                      'repair_min': prev_df['total_min'],
                                      'wait_min': prev_df['wait_min'],
                                      'machine_id': ['x'] * len(prev_df)}),
                        mc_count, 12)
                area_name = area_names.get(area, area)
                html_body = _build_html_email(
                    area, area_name, shift_name, date_str, start, end,
                    events_df, unclosed_df, util_pct, down_pct, lost_pct, prev_util)
                subject = f"[{area}] {shift_name} Shift Summary — {date_str}"
                _send_email(smtp, emails, subject, html_body)
                log.info(f"Sent {shift_name} shift email for {area} to {emails}")

        except Exception as e:
            log.error(f"Failed to send email for area {area}: {e}")


def _send_email(smtp_config, to_emails, subject, html_body):
    """Send HTML email via SMTP."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_config['from_addr'] or smtp_config['user']
    msg['To'] = ', '.join(to_emails)

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    with smtplib.SMTP(smtp_config['host'], smtp_config['port'], timeout=15) as server:
        if smtp_config['use_tls']:
            server.starttls()
            if smtp_config['user'] and smtp_config['password']:
                server.login(smtp_config['user'], smtp_config['password'])
        server.sendmail(msg['From'], to_emails, msg.as_string())


def send_test_email(area='DA', shift_name='Day', to_email=None):
    """Test function: send a single email for testing."""
    if to_email:
        os.environ['SHIFT_EMAIL_RECIPIENTS'] = f"{area}:{to_email}"
    os.environ['SHIFT_EMAIL_ENABLED'] = '1'
    send_shift_summary(shift_name)
