"""Union Bank of India (UBI) statement layout (from the statement screenshot).

Columns:
    Sl | Date | Particulars | Chq Num | Withdrawal | Deposit | Balance
"""

from .base import BankConfig

CONFIG = BankConfig(
    name="UBI",
    prefixes=["ubi"],
    date_headers=["date"],
    description_headers=["particulars", "narration", "description", "remarks"],
    debit_headers=["withdrawal", "debit"],
    credit_headers=["deposit", "credit"],
    balance_headers=["balance"],
    date_formats=["%d-%m-%y", "%d/%m/%y", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y"],
)
