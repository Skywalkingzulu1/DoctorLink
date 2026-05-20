// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * DoctorLink Escrow Contract on Somnia Agentic L1.
 * Handles appointment payments with 80/20 doctor/platform split.
 */
contract DoctorLinkEscrow {
    address public platform;
    uint256 public constant PLATFORM_FEE_PERCENT = 20;

    enum EscrowState { Pending, Held, Released, Refunded }

    struct Escrow {
        uint256 appointmentId;
        address patient;
        address doctor;
        uint256 amount;
        EscrowState state;
    }

    mapping(uint256 => Escrow) public escrows;

    event Deposited(uint256 appointmentId, address patient, address doctor, uint256 amount);
    event Released(uint256 appointmentId, address doctor, uint256 doctorAmount, uint256 platformFee);
    event Refunded(uint256 appointmentId, address patient, uint256 amount);

    modifier onlyPlatform() {
        require(msg.sender == platform, "Only platform");
        _;
    }

    modifier nonReentrant() {
        require(_status == 0, "Reentrancy");
        _status = 1;
        _;
        _status = 0;
    }

    uint256 private _status;

    constructor(address _platform) {
        platform = _platform;
        _status = 0;
    }

    function deposit(uint256 _appointmentId, address _doctor) external payable {
        require(msg.value > 0, "Amount must be > 0");
        require(escrows[_appointmentId].state == EscrowState.Pending, "Already deposited");

        escrows[_appointmentId] = Escrow({
            appointmentId: _appointmentId,
            patient: msg.sender,
            doctor: _doctor,
            amount: msg.value,
            state: EscrowState.Held
        });

        emit Deposited(_appointmentId, msg.sender, _doctor, msg.value);
    }

    function release(uint256 _appointmentId) external onlyPlatform nonReentrant {
        Escrow storage e = escrows[_appointmentId];
        require(e.state == EscrowState.Held, "Not held");

        uint256 doctorShare = (e.amount * (100 - PLATFORM_FEE_PERCENT)) / 100;
        uint256 platformFee = e.amount - doctorShare;

        e.state = EscrowState.Released;

        (bool doctorSent, ) = e.doctor.call{value: doctorShare}("");
        require(doctorSent, "Doctor transfer failed");

        (bool platformSent, ) = platform.call{value: platformFee}("");
        require(platformSent, "Platform transfer failed");

        emit Released(_appointmentId, e.doctor, doctorShare, platformFee);
    }

    function refund(uint256 _appointmentId) external onlyPlatform nonReentrant {
        Escrow storage e = escrows[_appointmentId];
        require(e.state == EscrowState.Held, "Not held");

        uint256 refundAmount = e.amount;
        e.state = EscrowState.Refunded;

        (bool sent, ) = e.patient.call{value: refundAmount}("");
        require(sent, "Refund failed");

        emit Refunded(_appointmentId, e.patient, refundAmount);
    }

    function getEscrowStatus(uint256 _appointmentId) external view returns (uint256, uint256, uint8) {
        Escrow storage e = escrows[_appointmentId];
        return (e.amount, e.state == EscrowState.Released ? e.amount : 0, uint8(e.state));
    }
}
