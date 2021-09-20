"""
    Functions helping with quantum circuit format conversion between abstract format and Braket format

    In order to produce an equivalent circuit for the target backend, it is necessary to account for:
    - how the gate names differ between the source backend to the target backend
    - how the order and conventions for some of the inputs to the gate operations may also differ
"""


def get_braket_gates():
    """
        Map gate name of the abstract format to the equivalent methods of the braket.circuits.Circuit class
        API and supported gates: https://amazon-braket-sdk-python.readthedocs.io/en/latest/_apidoc/braket.circuits.circuit.html
    """

    from braket.circuits import Circuit as BraketCircuit

    GATE_BRAKET = dict()
    GATE_BRAKET["H"] = BraketCircuit.h
    GATE_BRAKET["X"] = BraketCircuit.x
    GATE_BRAKET["Y"] = BraketCircuit.y
    GATE_BRAKET["Z"] = BraketCircuit.z
    GATE_BRAKET["S"] = BraketCircuit.s
    GATE_BRAKET["T"] = BraketCircuit.t
    GATE_BRAKET["RX"] = BraketCircuit.rx
    GATE_BRAKET["RY"] = BraketCircuit.ry
    GATE_BRAKET["RZ"] = BraketCircuit.rz
    GATE_BRAKET["CNOT"] = BraketCircuit.cnot
    # GATE_BRAKET["MEASURE"] = ? (mid-circuit measurement currently unsupported?)

    return GATE_BRAKET


def translate_braket(source_circuit):
    """ Take in an abstract circuit, return a quantum circuit object as defined in the Python Braket SDK

        Args:
            source_circuit: quantum circuit in the abstract format
        Returns:
            target_circuit (braket.circuits.Circuit): quantum circuit in Python Braket SDK format
    """

    from braket.circuits import Circuit as BraketCircuit

    GATE_BRAKET = get_braket_gates()
    target_circuit = BraketCircuit()

    # Map the gate information properly. Different for each backend (order, values)
    for gate in source_circuit._gates:
        if gate.name in {"H", "X", "Y", "Z", "S", "T"}:
            (GATE_BRAKET[gate.name])(target_circuit, gate.target)
        elif gate.name in {"RX", "RY", "RZ"}:
            (GATE_BRAKET[gate.name])(target_circuit, gate.target, gate.parameter)
        elif gate.name in {"CNOT"}:
            (GATE_BRAKET[gate.name])(target_circuit, control=gate.control, target=gate.target)
        # elif gate.name in {"MEASURE"}:
        # implement if mid-circuit measurement available through Braket later on
        else:
            raise ValueError(f"Gate '{gate.name}' not supported on backend braket")
    return target_circuit
