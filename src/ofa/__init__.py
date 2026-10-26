"""ofa: the only component that touches Odoo (plan, apply, test on demo databases)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ODOO_SERIES = "20.0"
