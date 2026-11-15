"""
Locate a ChemSep installation and read compound data from its binary pure-component library (pcd/chemsep1.pcd).

ChemSep (https://www.chemsep.org) is a free column simulator by Harry Kooijman and Ross Taylor; we use its LITE edition's column solver and
its component library. Nothing from ChemSep is redistributed here: install it on the machine that runs the simulator.

Library layout (1024-byte blocks): a compound starts at block `offset`; byte 0 is 0x54, bytes 1-2 the library index, byte 3 the name length,
then the name; float32 fields at fixed offsets give critical constants, acentric factor and correlation blocks.
"""
import glob
import os
import struct

SCALARS = {"criticalTemperature": 106, "criticalPressure": 110, "acentricFactor": 146}
IDEAL_GAS_CP = 6                      # index of the ideal-gas heat-capacity correlation among the record's 17 correlation blocks
CORR_START, CORR_LEN = 194, 29        # per block: [equation number byte][Tmin f32][Tmax f32][5 coefficients f32]
CAS_OFFSET = 839                      # Pascal string


def find_chemsep():
    """ChemSep install directory: $CHEMSEP_DIR, else the newest ChemSepL8v* under Program Files or the user's local app data."""
    env = os.environ.get("CHEMSEP_DIR")
    if env:
        return env
    cands = []
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.environ.get("LOCALAPPDATA", "")):
        if root:
            cands += glob.glob(os.path.join(root, "ChemSepL8v*"))
    cands = [c for c in cands if os.path.exists(os.path.join(c, "bin", "co-col2.exe"))]
    return sorted(cands)[-1] if cands else None


def chemsep_exe(chemsep_dir=None):
    d = chemsep_dir or find_chemsep()
    if not d:
        return None
    p = os.path.join(d, "bin", "co-col2.exe")
    return p if os.path.exists(p) else None


def _f(rec, o):
    return struct.unpack("<f", rec[o:o + 4])[0]


class Library:
    def __init__(self, chemsep_dir=None):
        self.dir = chemsep_dir or find_chemsep()
        if not self.dir:
            raise FileNotFoundError("ChemSep not found: install ChemSep LITE (chemsep.org) or set CHEMSEP_DIR")
        self.path = os.path.join(self.dir, "pcd", "chemsep1.pcd")
        self.b = open(self.path, "rb").read()
        self.by_name = {}
        for blk in range(len(self.b) // 1024):
            r = self.b[blk * 1024:blk * 1024 + 40]
            if r[0] == 0x54 and 0 < r[3] < 36:
                try:
                    name = r[4:4 + r[3]].decode("latin1")
                except Exception:  # noqa: BLE001
                    continue
                self.by_name.setdefault(name.lower(), (blk, struct.unpack("<H", r[1:3])[0]))

    def find(self, name):
        """(library offset, library index) of a compound by its ChemSep name (case-insensitive)."""
        return self.by_name[name.lower()]

    def record(self, name):
        off, idx = self.find(name)
        rec = self.b[off * 1024:off * 1024 + 2048]
        o = CORR_START + CORR_LEN * IDEAL_GAS_CP
        n = rec[839]
        return {"name": rec[4:4 + rec[3]].decode("latin1"), "offset": off, "index": idx, "cas": rec[CAS_OFFSET + 1:CAS_OFFSET + 1 + n].decode("latin1"),
                "Tc": _f(rec, SCALARS["criticalTemperature"]), "Pc": _f(rec, SCALARS["criticalPressure"]), "omega": _f(rec, SCALARS["acentricFactor"]),
                "cp_eq": int(rec[o]), "cp_coef": [_f(rec, o + 9 + 4 * j) for j in range(5)]}
