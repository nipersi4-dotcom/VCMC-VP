from pathlib import Path

ROOT = Path(__file__).resolve().parent
required = [
    ROOT/'server.py',
    ROOT/'test_master_build.py',
    ROOT/'test_roadmap_3_10.py',
    ROOT/'Dockerfile',
    ROOT/'render.yaml',
    ROOT/'requirements.txt',
    ROOT/'ROADMAP_10_ACCEPTANCE.md',
    ROOT/'VCMC_7_STAGE_COMPLETION_GATE.md',
]
for p in required:
    assert p.is_file(), f'MISSING: {p}'
text=(ROOT/'VCMC_7_STAGE_COMPLETION_GATE.md').read_text()
for phrase in ['CLAIM != EVIDENCE','READY != PROVEN','UNKNOWN != FAILED','VCMC != PJP','ALLOCATION LOGIC != PAYMENT EXECUTION']:
    assert phrase in text
print('VCMC-VP 7-STAGE BUILD GATE: PASS')
