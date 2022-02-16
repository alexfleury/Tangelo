# Copyright 2021 Good Chemistry Company.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module implements functions to create the direct interaction set (DIS)
of generators for the qubit coupled cluster (QCC) ansatz and is based on Ref. 1.
The DIS consists of generator groups that are characterized by the magnitude of
the gradient of the QCC energy functional with respect to a variational parameter
tau, |dEQCC/dtau|. Nonzero values of |dEQCC/dtau| imply that an individual
generator will contribute to variational energy lowering. The number of DIS groups
cannot exceed the number of Hamiltonian terms, N, and each DIS group contains
2^nq - 1 generators, where nq is the number of qubits, all with identical values
of |dEQCC/dtau|. By constructing the DIS, it is possible to identify O(N * (2^nq - 1))
generators that are strong energy-lowering candidates for the QCC ansatz at a
cost of O(N) gradient evaluations. In contrast, a brute-force strategy requires
O(4^nq) gradient evaluations.

Refs:
    1. I. G. Ryabinkin, R. A. Lang, S. N. Genin, and A. F. Izmaylov.
        J. Chem. Theory Comput. 2020, 16, 2, 1055–1063.
"""

from itertools import combinations

from tangelo.toolboxes.operators.operators import QubitOperator
from ._qubit_mf import get_op_expval


def construct_dis(pure_var_params, qubit_ham, qcc_deriv_thresh, verbose=False):
    """Construct the DIS of QCC generators, which proceeds as follows:
    1. Identify the flip indices of all Hamiltonian terms and group terms by flip indices.
    2. Construct a representative generator using flip indices from each candidate DIS group
       and evaluate dEQCC/dtau for all Hamiltonian terms.
    3. For each candidate DIS group, sum dEQCC/dtau for all Hamiltonian terms.
       If |dEQCC/dtau| >= thresh add the candidate DIS group to the DIS.
    4. For all DIS groups, create a complete set of generators made from Pauli X and and an
       odd number of Y operators.

    Args:
        pure_var_params (numpy array of float): A purified QMF variational parameter set.
        qubit_ham (QubitOperator): A qubit Hamiltonian.
        qcc_deriv_thresh (float): Threshold value of |dEQCC/dtau| so that if |dEQCC/dtau| >=
            qcc_deriv_thresh for a generator, add its candidate group to the DIS.
        verbose (bool): Flag for QCC verbosity.

    Returns:
        list of list: the DIS of QCC generators.
    """

    # Use a qubit Hamiltonian and purified QMF parameter set to construct the DIS
    dis, dis_groups = [], get_dis_groups(pure_var_params, qubit_ham, qcc_deriv_thresh)
    if dis_groups:
        if verbose:
            print(f"The DIS contains {len(dis_groups)} unique generator group(s).\n")
        for i, dis_group in enumerate(dis_groups):
            dis_group_idxs = [int(idxs) for idxs in dis_group[0].split(" ")]
            dis_group_gens = get_gens_from_idxs(dis_group_idxs)
            dis.append(dis_group_gens)
            if verbose:
                print(f"DIS group {i} | group size = {len(dis_group_gens)} | "
                      f"flip indices = {dis_group_idxs} | |dEQCC/dtau| = "
                      f"{abs(dis_group[1])} a.u.\n")
    else:
        raise ValueError(f"The DIS is empty: there are no candidate DIS groups where "
                         f"|dEQCC/dtau| >= {qcc_deriv_thresh} a.u. Terminate the QCC simulation.\n")
    return dis


def get_dis_groups(pure_var_params, qubit_ham, qcc_deriv_thresh):
    """Construct unique DIS groups characterized by the flip indices and |dEQCC/dtau|.

    Args:
        pure_var_params (numpy array of float): A purified QMF variational parameter set.
        qubit_ham (QubitOperator): A qubit Hamiltonian.
        qcc_deriv_thresh (float): Threshold value of |dEQCC/dtau| so that if |dEQCC/dtau| >=
            qcc_deriv_thresh for a generator, add its candidate group to the DIS.

    Returns:
        list of tuple: the DIS group flip indices (str) and signed value of dEQCC/dtau (float).
    """

    # Get the flip indices from qubit_ham and compute the gradient dEQCC/dtau
    qham_gen = ((qham_items[0], (qham_items[1], pure_var_params))
                 for qham_items in qubit_ham.terms.items())
    flip_idxs = list(filter(None, (get_idxs_deriv(q_gen[0], *q_gen[1]) for q_gen in qham_gen)))

    # Group Hamiltonian terms with the same flip indices and sum signed dEQCC/tau values
    candidates = dict()
    for idxs in flip_idxs:
        deriv_old = candidates.get(idxs[0], 0.)
        candidates[idxs[0]] = idxs[1] + deriv_old

    # Return a sorted list of flip indices and signed dEQCC/dtau values for each DIS group
    dis_groups = [idxs_deriv for idxs_deriv in candidates.items()
                  if abs(idxs_deriv[1]) >= qcc_deriv_thresh]
    return sorted(dis_groups, key=lambda deriv: abs(deriv[1]), reverse=True)


def get_idxs_deriv(qham_term, *qham_qmf_data):
    """Find the flip indices of a qubit Hamiltonian term by identifying the indices
    of any X and Y operators that are present. A representative generator is then
    built with a Pauli Y operator acting on the first flip index and then Pauli X
    operators acting on the remaining flip indices. Then dEQCC/dtau is evaluated as
    dEQCC_dtau = -i/2 <QMF|[H, gen]|QMF> = -i <QMF|H * gen|QMF>.

    Args:
        qham_term (tuple of tuple): The Pauli operators and indices of a QubitOperator term.
        qham_qmf_data (tuple): The coefficient of a QubitOperator term and a purified QMF
            variational parameter set (numpy array of float).

    Returns:
        tuple or None: return a tuple of the flip indices (str) and the signed value of
            dEQCC/dtau (float) if at least two flip indices were found. Otherwise return None.
    """

    coef, pure_params = qham_qmf_data
    idxs, gen_list, idxs_deriv = "", [], None
    for pauli_factor in qham_term:
        # The indices of X and Y operators are flip indices
        idx, pauli_op = pauli_factor
        if "X" in pauli_op or "Y" in pauli_op:
            gen = (idx, "Y") if idxs == "" else (idx, "X")
            idxs = idxs + f" {idx}" if idxs != "" else f"{idx}"
            gen_list.append(gen)
    # Generators must have at least two flip indices
    if len(gen_list) > 1:
        qham_gen_comm = QubitOperator(qham_term, -1j * coef)
        qham_gen_comm *= QubitOperator(tuple(gen_list), 1.)
        deriv = get_op_expval(qham_gen_comm, pure_params).real
        idxs_deriv = (idxs, deriv)
    return idxs_deriv


def get_gens_from_idxs(group_idxs):
    """Given the flip indices of a DIS group, create all possible Pauli words made
    from Pauli X and an odd number of Y operators acting on qubits indexed by the
    flip indices.

    Args:
        group_idxs (str): A set of flip indices for a DIS group.

    Returns:
        list of QubitOperator: DIS group generators.
    """

    dis_group_gens = []
    for n_y in range(1, len(group_idxs), 2):
        # Create combinations of odd numbers of flip indices for the Pauli Y operators
        for xy_idx in combinations(group_idxs, n_y):
            # If a flip index idx matches xy_idx, add a Y operator
            gen_list = [(idx, "Y") if idx in xy_idx else (idx, "X") for idx in group_idxs]
            dis_group_gens.append(QubitOperator(tuple(gen_list), 1.))
    return dis_group_gens