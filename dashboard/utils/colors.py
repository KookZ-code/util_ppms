# Microchip corporate color palette
# Source: .claude/skills/data-to-slides/presentation-style.md

# Primary
PRIMARY_BLUE = '#0E3689'
LIGHT_BLUE = '#1D9CE4'
ORANGE = '#FD7F20'
GREEN = '#5EBF33'
RED = '#CC0000'
PURPLE = '#702076'
YELLOW = '#FFD53A'

# Text & background
DARK_TEXT = '#0A0B0F'
DARK_GRAY = '#4A4A4A'
MED_GRAY = '#8A8A8A'
LIGHT_GRAY = '#D9D9D9'
BG_GRAY = '#F7F7F7'
WHITE = '#FFFFFF'

# Semantic status mapping
STATUS_COLORS = {
    'Running': GREEN,
    'Run': GREEN,
    'Idle': ORANGE,
    'Down': RED,
    'Standby': LIGHT_BLUE,
    'Maintenance': PURPLE,
    'PM': PURPLE,
    'Unknown': MED_GRAY,
}

# Chart color sequence for Plotly
CHART_COLORS = [PRIMARY_BLUE, LIGHT_BLUE, GREEN, ORANGE, RED, PURPLE, YELLOW]

# Job type color mapping (matches vw_job_nokey job_type values)
JOB_TYPE_COLORS = {
    'M/C DOWN': RED,
    'ENGINEERING DOWN': '#990000',
    'FACILITY DOWN': ORANGE,
    'PM': PURPLE,
    'SETUP': LIGHT_BLUE,
    'SETUP BY OPERATOR': '#17A2B8',
    'CONVERT': YELLOW,
    'CLEAN MOLD': GREEN,
    'CHANGE CAP': MED_GRAY,
}
