from collections.abc import Sequence
from itertools import dropwhile

import numpy as np


def mol2geom(mol: Sequence[str]) -> tuple[np.ndarray, np.ndarray, dict[int, str]]:
    length_atoms, length_bonds, *_ = mol[0].split()
    matrix = np.zeros((int(length_atoms), 3))
    bonds = np.zeros((int(length_bonds), 3), dtype=int)
    atoms: dict[int, str] = {}
    stop_idx = None
    for i, line in enumerate(mol[1:]):
        if i < int(length_atoms):
            x, y, z, atom, *_ = line.split()
            matrix[i, :] = float(x), float(y), float(z)
            atoms[i] = atom
            if atom == 'H':
                if stop_idx is None:
                    stop_idx = i
                continue
        else:
            split = line.split()
            if len(split) < 4:
                break
            id1_str, id2_str, multiplicity, *_ = split
            id1 = int(id1_str) - 1
            id2 = int(id2_str) - 1
            # skip hydrogen atoms/bonds, they do not need to be visualized
            if atoms.get(id1) == 'H' or atoms.get(id2) == 'H':
                continue
            idx = i - int(length_atoms)
            bonds[idx, :] = id1, id2, int(multiplicity)

    return matrix[:stop_idx, :], bonds, atoms


if __name__ == "__main__":
    with open("molfiles/gly.mol") as f:
        _ = dropwhile(lambda x: 'V2000' not in x, f.readlines())
    print(mol2geom(list(_)))
