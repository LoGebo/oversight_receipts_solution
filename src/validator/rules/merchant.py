"""Merchant rules: MCC-01 (high-risk MCC -> exception) and MCC-02 (medium-risk MCC -> review signal).

MCC-03 is a clarification of ALC-01/02/03 (a bar is on premises), implemented in alcohol.py.
Both checks look only at the receipt's MCC, so they cite no lines (EXC-04: whole-receipt rule).
"""
from validator.check import Check

HIGH = {"5921", "5993", "7995", "7297", "5944"}
MEDIUM = {"5813", "5912", "5311", "5411", "5732"}  # any MCC not listed is low risk
RULE_IDS = ("MCC-01", "MCC-02")


def merchant_checks(receipt: dict) -> list[Check]:
    mcc = str(receipt["mcc"]).strip()
    if mcc in HIGH:
        mcc01 = Check("MCC-01", "fired", severity="high", detail=f"MCC {mcc} is a high-risk merchant category")
    else:
        mcc01 = Check("MCC-01", "not_fired", detail=f"MCC {mcc} is not high risk")
    if mcc in MEDIUM:
        mcc02 = Check("MCC-02", "fired", kind="signal", detail=f"MCC {mcc} is a medium-risk merchant category")
    else:
        mcc02 = Check("MCC-02", "not_fired", kind="signal", detail=f"MCC {mcc} is not medium risk")
    return [mcc01, mcc02]
