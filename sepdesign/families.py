"""
A component set on ChemSep's Peng-Robinson 76 column: thermodynamic constants from ChemSep's library, binary interaction parameters from
ChemSep's DECHEMA table (ipd/pr.ipd; a pair without an entry has kij = 0), and the column input-file template with both filled in.

    fam = pr_family(["Ethane", "Propane", ...])     # needs ChemSep installed (reads its library)
"""
import os
import re

import numpy as np

from sepdesign.chemsep_lib import Library
from sepdesign.thermo import PRThermo

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "column_pr76.sep.tmpl")


def read_pr_ipd(path):
    """{(cas_a, cas_b): [(k12, comment), ...]}: ChemSep's Peng-Robinson interaction table (several temperature ranges per pair)."""
    out = {}
    started = False
    for line in open(path, encoding="latin1"):
        if line.startswith("[IPD]"):
            started = True
            continue
        if not started or line.lstrip().startswith(("#", "Comment")) or not line.strip():
            continue
        t = line.split(None, 3)
        if len(t) < 3 or not re.match(r"^\d+-\d+-\d$", t[0]) or not re.match(r"^\d+-\d+-\d$", t[1]):
            continue
        try:
            k = float(t[2])
        except ValueError:
            continue
        out.setdefault((t[0], t[1]), []).append((k, t[3].strip() if len(t) > 3 else ""))
        out[(t[1], t[0])] = out[(t[0], t[1])]
    return out


def _covers(comment, T):
    m = re.search(r"T=([^ ]*?)K", comment)
    if not m:
        return False
    for part in m.group(1).split(","):
        r = re.match(r"^([\d.]+)-([\d.]+)$", part.strip())
        if r and float(r.group(1)) <= T <= float(r.group(2)):
            return True
    return False


def choose_kij(entries, T=350.0):
    """One k12 for a pair: the entry whose temperature range covers T, else the first listed."""
    for k, c in entries:
        if _covers(c, T):
            return k
    return entries[0][0]


class Family:
    def __init__(self, names, cas, thermo, kij_pairs, sep_template):
        self.names, self.cas, self.thermo, self.kij_pairs, self.sep_template = names, cas, thermo, kij_pairs, sep_template
        self.n = len(names)


def pr_family(names, chemsep_dir=None, kij_T=350.0):
    lib = Library(chemsep_dir)
    recs = [lib.record(n) for n in names]
    n = len(recs)
    ipd = read_pr_ipd(os.path.join(lib.dir, "ipd", "pr.ipd"))
    kij = np.zeros((n, n))
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            e = ipd.get((recs[i]["cas"], recs[j]["cas"]))
            if e:
                k = choose_kij(e, kij_T)
                kij[i, j] = kij[j, i] = k
                if k != 0.0:
                    pairs.append((i + 1, j + 1, k, f"{recs[i]['name']}/{recs[j]['name']}"))
    assert all(r["Tc"] > 0 and r["Pc"] > 0 for r in recs), "a compound has no critical data in the library"
    thermo = PRThermo({"names": [r["name"] for r in recs], "Tc": [r["Tc"] for r in recs], "Pc": [r["Pc"] for r in recs],
                       "omega": [r["omega"] for r in recs], "cp": [(r["cp_eq"], r["cp_coef"]) for r in recs], "kij": kij})
    comps = f"{n} Number of Components\n" + "".join(
        f"{r['offset']} {r['index']} Library Offset, Index CAS={r['cas']} CID={r['name']}\nName={r['name']}\nLib={lib.path.lower()}\n" for r in recs)
    kij_block = ("[Peng-Robinson 76 Data]\n      i      j          kij  Component Component\n"
                 + "".join(f"{i:7d}{j:7d}{k:12.4f}  {lab}\n" for i, j, k, lab in pairs))
    raw = open(TEMPLATE, encoding="latin-1", newline="").read().replace("\r\n", "\n")      # a Windows checkout may have CRLF line endings
    text = raw.replace("{{COMPONENTS}}", comps.rstrip("\n")).replace("{{KIJ}}", kij_block.rstrip("\n"))
    text = text.replace("{{CHEMSEP}}", lib.dir)
    return Family([r["name"] for r in recs], [r["cas"] for r in recs], thermo, pairs, text)
