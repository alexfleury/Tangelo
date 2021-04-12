"""Tools to define a reference state under a specified qubit-mapping, and
translate into a Circuit."""
import numpy as np
import warnings

from agnostic_simulator import Gate, Circuit

from openfermion.transforms import bravyi_kitaev_code

available_mappings = {'JW', 'BK', 'SCBK'}

def get_vector(n_qubits, n_electrons, mapping, updown=False):
    """Get integer vector corresponding to Hartree Fock reference
    state. Reference state will occupy up to the n_electron-th 
    molecular orbital. Depending on convention, basis is ordered
    alternating spin-up/spin-down (updown = False), or all up, then 
    all down (updown = True). 

    Args:
        n_qubits (int): number of qubits in register
        n_electrons (int): number of electrons in system
        mapping (string): specify mapping, see mapping_transform.py for options
            'JW' (Jordan Wigner), or 'BK' (Bravyi Kitaev), or 'SCBK' (symmetry-conserving Bravyi Kitaev)
        updown (boolean): if True, all up, then all down, if False, alternating spin
            up/down

    Returns:
        vector (numpy array of int): binary integer array indicating occupation of
            each spin-orbital.
    """
    if mapping.upper() not in available_mappings:
        raise ValueError(f'Invalid mapping selection. Select from: {available_mappings}')

    vector = np.zeros(n_qubits, dtype=int)
    vector[:n_electrons] = 1
    if updown:
        vector = np.concatenate((vector[::2], vector[1::2]))

    if mapping.upper() == 'JW':
        return vector
    elif mapping.upper() == 'BK':
        return do_bk_transform(vector)
    elif mapping.upper() == 'SCBK':
        if not updown:
            warnings.warn("Symmetry-conserving Bravyi-Kitaev enforces all spin-up followed by all spin-down ordering.", RuntimeWarning)
        return do_scbk_transform(n_qubits, n_electrons)


def do_bk_transform(vector):
    """Apply Bravyi-Kitaev transformation to fermion occupation vector.
    Currently, simple wrapper on openfermion tools.

    Args:
        vector (numpy array of int): fermion occupation vector

    Returns:
        vector_bk (numpy array of int): qubit-encoded occupation vector.
    """
    mat = bravyi_kitaev_code(len(vector)).encoder.toarray()
    vector_bk = np.mod(np.dot(mat, vector), 2)
    return vector_bk


def do_scbk_transform(n_qubits, n_electrons):
    """Instantiate qubit vector for symmetry-conserving 
    Bravyi-Kitaev transformation. Based on implementation by Yukio Kawashima
    in DMET project. 

    Args:
        n_qubits (int): number of qubits in register.
        n_electrons (int): number of fermions occupied

    Returns:
        vector (numpy array of int): qubit-encoded occupation vector
    """
    n_alpha, n_orb = n_electrons//2, (n_qubits-2)//2
    vector = np.zeros(n_qubits - 2, dtype=int)
    if n_alpha >= 1:
        vector[:n_alpha - 1] = 1
        vector[n_orb:n_orb + n_alpha - 1] = 1
    return vector


def vector_to_circuit(vector):
    """Translate occupation vector into a circuit. Each
    occupied state corresponds to an X-gate on the associated
    qubit index. 

    Args:
        vector (numpy array of int): occupation vector

    Returns:
        circuit (Circuit): instance of agnostic_simulator Circuit class
    """
    circuit = Circuit()

    for index, occupation in enumerate(vector):
        if occupation:
            gate = Gate('X', target=index)
            circuit.add_gate(gate)
        
    return circuit
