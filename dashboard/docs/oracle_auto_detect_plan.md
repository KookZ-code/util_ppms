# Oracle Auto-Detect Mode — Implementation Plan

**Status:** Draft — awaiting user approval
**Author:** Architect (planner agent) + Main Claude
**Date:** 2026-05-05
**Target file:** `oracle_db.py`

---

## 1. Summary

ปัจจุบัน `oracle_db.py` บังคับใช้ **Thick mode** ของ `python-oracledb` ซึ่งต้องมี Oracle Instant Client ติดตั้งบนเครื่อง และ bitness ต้องตรงกับ Python เมื่อ clone source ไป server ที่ไม่มี Instant Client (หรือมี bit ไม่ตรง) ระบบจะ fail ด้วย error `DPI-1047` หน้า ISO/FS โหลดข้อมูลไม่ได้

**วิธีแก้:** เปลี่ยน `_init_client()` เป็น **auto-detect** — ถ้าตั้งค่า `ORA_CLIENT_LIB` ไว้ ลอง Thick mode ก่อน, ถ้า fail จะ fallback เป็น Thin mode อัตโนมัติ (pure Python, ไม่ต้องติดตั้งอะไรเพิ่ม) ถ้าไม่ได้ตั้ง `ORA_CLIENT_LIB` → ใช้ Thin mode เลย

---

## 2. Problem

### Root Cause
```
oracle_db.py:25-33  →  oracledb.init_oracle_client(lib_dir=ORA_CLIENT_LIB)
                       └─ requires Oracle Instant Client binaries
                          └─ bitness MUST match Python (32 vs 64-bit)
                             └─ FAILS on server without Instant Client
```

### Error Message ที่มักเจอ
- `DPI-1047: Cannot locate a 64-bit Oracle Client library`
- `DPI-1047: 64-bit Oracle Client library cannot be loaded`

### Impact
- หน้า `ISO` และ `FS` ไม่แสดงข้อมูลบน production server
- Dev เครื่องเดิม (มี Instant Client ติดตั้ง) ยังใช้งานได้ปกติ → ยากต่อการ reproduce
- ต้องติดตั้ง Instant Client แยกทุกครั้งที่ deploy ไป server ใหม่

---

## 3. Proposed Solution — Auto-Detect

### Decision Tree

```
_init_client() เรียก
       ↓
ORA_CLIENT_LIB มีค่าไหม?
       │
   ┌───┴───┐
   NO      YES
   │        │
   │        └─→ ลอง oracledb.init_oracle_client(lib_dir=...)
   │              │
   │         ┌────┴────┐
   │       success    exception
   │         │          │
   │         │          └─→ log warning, ไป Thin mode
   │         │
   │         └─→ log info "Thick mode active"
   │
   └─→ ไป Thin mode เลย (log info "Thin mode — no ORA_CLIENT_LIB set")
       │
       └─→ return (python-oracledb default = Thin)
```

### ทำไมเลือกวิธีนี้

| เกณฑ์ | Auto-Detect | Thin only | Thick only (ปัจจุบัน) |
|-------|-------------|-----------|----------------------|
| ใช้บน server ใหม่ได้ทันที | ✅ | ✅ | ❌ |
| เก็บ performance ของ Thick (dev) | ✅ | ⚠️ เล็กน้อย | ✅ |
| Backward compatible | ✅ | ✅ | baseline |
| Config change | ❌ ไม่ต้อง | ✅ ต้องลบ | baseline |
| โค้ดเปลี่ยนน้อยที่สุด | ⚠️ ~15 บรรทัด | ✅ ~5 บรรทัด | — |

---

## 4. Code Changes

### 4.1 `oracle_db.py` — แก้ `_init_client()`

**BEFORE (lines 17, 25-33):**

```python
_client_initialized = False
_lock = threading.Lock()

# ...

def _init_client():
    global _client_initialized
    if _client_initialized:
        return
    import oracledb
    from config import ORA_CLIENT_LIB
    if ORA_CLIENT_LIB:
        oracledb.init_oracle_client(lib_dir=ORA_CLIENT_LIB)
    _client_initialized = True
```

**AFTER:**

```python
_client_initialized = False
_client_mode = None  # 'thick' | 'thin' — for diagnostics/logging
_lock = threading.Lock()

# ...

def _init_client():
    """Initialize the Oracle client in thick mode if ORA_CLIENT_LIB is set
    and the Instant Client loads successfully; otherwise fall back to
    thin mode (pure Python, no Instant Client required).

    Idempotent — safe to call multiple times.
    """
    global _client_initialized, _client_mode
    if _client_initialized:
        return
    import oracledb
    from config import ORA_CLIENT_LIB

    if ORA_CLIENT_LIB:
        try:
            oracledb.init_oracle_client(lib_dir=ORA_CLIENT_LIB)
            _client_mode = 'thick'
            log.info("Oracle client: thick mode (lib_dir=%s)", ORA_CLIENT_LIB)
        except Exception as e:
            _client_mode = 'thin'
            log.warning(
                "Oracle thick mode failed (%s) — falling back to thin mode. "
                "This is expected on servers without Oracle Instant Client "
                "or with a bitness mismatch.", e
            )
    else:
        _client_mode = 'thin'
        log.info("Oracle client: thin mode (ORA_CLIENT_LIB not set)")

    _client_initialized = True
```

**Key points:**
- ใช้ `try/except Exception` กว้างๆ เพราะ init_oracle_client อาจ raise `DPI-1047`, `DPI-1072`, `OSError`, `AttributeError` หรือ error อื่นๆ ตาม platform
- `_client_mode` เก็บไว้เพื่อ debug ง่าย (สามารถ expose ผ่าน health-check endpoint ได้ในอนาคต — out of scope)
- Log ระดับ `info` เมื่อสำเร็จ, `warning` เมื่อ fallback → ops ดู log แล้วเข้าใจสถานะทันที
- Idempotency ยังอยู่ (`_client_initialized` guard)

### 4.2 Files Touched

| File | Change | Lines affected |
|------|--------|----------------|
| `oracle_db.py` | แก้ `_init_client()` + เพิ่มตัวแปร `_client_mode` | ~15 lines |
| `config.py` | **ไม่ต้องแก้** — เก็บ `ORA_CLIENT_LIB` ไว้เป็น optional | 0 |
| `.env` / `.env.example` | **ไม่ต้องแก้** | 0 |
| `requirements.txt` | **ไม่ต้องแก้** — `oracledb` รองรับทั้ง 2 mode อยู่แล้ว | 0 |

---

## 5. Thread Safety

- `_init_client()` ถูกเรียกจาก 2 จุด: `_get_connection()` (line 39) และ `fetch_oracle_live_status()` (line 206 — redundant แต่ไม่แก้ scope นี้)
- ทั้ง 2 paths มี `try/except` ครอบอยู่แล้ว (`_load_all` line 101-104, `fetch_oracle_live_status` line 286-288) → ถ้า thick mode fail และ thin mode ก็ fail (เช่น DSN ผิด) ระบบยังไม่ crash
- `_client_initialized` flag ป้องกันการเรียก `init_oracle_client()` ซ้ำ — oracledb จะ raise error ถ้าเรียกซ้ำ
- การ read/write `_client_initialized` ไม่ได้อยู่ใน lock แต่ Python GIL + idempotent operation → race ไม่เสียหาย (อย่างแย่สุดคือ log 2 ครั้ง)

---

## 6. Testing Checklist

| # | Scenario | Expected Result |
|---|----------|-----------------|
| 1 | Dev เครื่องปัจจุบัน (มี Instant Client) — ตั้ง `ORA_CLIENT_LIB` ถูก | Log: "thick mode"; ISO/FS ดึงข้อมูลได้ |
| 2 | Server ไม่มี Instant Client — ตั้ง `ORA_CLIENT_LIB` ชี้ไป path ผิด | Log: "thick mode failed — falling back to thin"; ISO/FS ดึงข้อมูลได้ |
| 3 | Server ไม่ได้ตั้ง `ORA_CLIENT_LIB` (empty) | Log: "thin mode (ORA_CLIENT_LIB not set)"; ISO/FS ดึงข้อมูลได้ |
| 4 | `ORA_ENABLED=0` | ทั้ง `fetch_oracle_data` และ `fetch_oracle_live_status` คืน `None` — ไม่เรียก `_init_client` |
| 5 | DSN ผิด (connect fail) | Log: thin mode succeeded + connect error → หน้า ISO/FS แสดง empty state ไม่ crash |
| 6 | รัน dashboard แล้ว refresh 3 ครั้ง | `init_oracle_client` ถูกเรียกแค่ครั้งเดียว (check log) |
| 7 | `python -m py_compile oracle_db.py` | ไม่มี syntax error |
| 8 | Grep `_client_mode` | ค่าเป็น `'thick'` หรือ `'thin'` ชัดเจน (ไม่ใช่ None) หลัง init |

---

## 7. Rollback Plan

```bash
git log --oneline -5          # หา commit hash
git revert <commit-hash>       # revert แบบ safe (ไม่ลบ history)
```

**ถ้า rollback แล้วยัง fail** → ปัญหาอยู่ที่ DSN / credentials ไม่ใช่ mode การเชื่อมต่อ

---

## 8. Risk Assessment

| ด้าน | ระดับ | เหตุผล |
|------|-------|--------|
| **Overall** | 🟢 **Low** | |
| Functionality regression | 🟢 Low | Thin mode รองรับ features ที่ code ปัจจุบันใช้ครบ (SELECT, bind params, prefetchrows, arraysize) |
| Performance | 🟡 Low-Med | Thin mode ช้ากว่า Thick ~5-15% สำหรับ bulk fetch แต่ code ใช้ background thread + cache 10 นาที → user ไม่รู้สึก |
| Security | 🟢 Low | ไม่เปลี่ยน credential handling, ไม่เปลี่ยน network path |
| Thread safety | 🟢 Low | Idempotent, GIL protected |
| Deploy risk | 🟢 Low | ไม่ต้อง migrate data, ไม่ต้อง restart service พิเศษ |

---

## 9. Out of Scope

- ❌ ไม่แก้ `_init_client()` ที่ถูกเรียกซ้ำใน `fetch_oracle_live_status` line 206 (ปลอดภัยอยู่แล้ว เพราะ idempotent — จะ refactor ภายหลัง)
- ❌ ไม่แก้ connection pooling (ปัจจุบันสร้าง connection ใหม่ทุกครั้ง — เรื่องแยก)
- ❌ ไม่แก้ cache TTL (ยัง 600s เหมือนเดิม)
- ❌ ไม่เพิ่ม health-check endpoint สำหรับดู `_client_mode`
- ❌ ไม่เปลี่ยน `config.py` / `.env` — backward compatible เต็มรูปแบบ

---

## 10. Approval

- [ ] User reviewed plan
- [ ] User approved → proceed to Coder step

หลัง approve แล้ว ทีมจะดำเนินการตามลำดับ:
**Coder → Reviewer (python-reviewer) → แก้ตาม review (ถ้ามี) → Git commit (ไม่ push)**
