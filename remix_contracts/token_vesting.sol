// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract TokenVesting {
    address public owner;
    IERC20 public token;

    struct VestingSchedule {
        address beneficiary;
        uint256 totalAmount;
        uint256 startTime;
        uint256 cliffDuration;
        uint256 duration;
        uint256 released;
    }

    VestingSchedule[] public schedules;
    mapping(address => uint256[]) public beneficiarySchedules;

    event ScheduleCreated(uint256 indexed scheduleId, address indexed beneficiary, uint256 amount);
    event TokensReleased(uint256 indexed scheduleId, address indexed beneficiary, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor(address _token) {
        owner = msg.sender;
        token = IERC20(_token);
    }

    function createSchedule(
        address beneficiary,
        uint256 amount,
        uint256 startTime,
        uint256 cliffDuration,
        uint256 duration
    ) external onlyOwner {
        require(beneficiary != address(0), "Zero beneficiary");
        require(amount > 0, "Zero amount");
        require(duration > 0, "Zero duration");
        require(cliffDuration <= duration, "Cliff > duration");

        token.transferFrom(msg.sender, address(this), amount);

        uint256 scheduleId = schedules.length;
        schedules.push(VestingSchedule({
            beneficiary: beneficiary,
            totalAmount: amount,
            startTime: startTime == 0 ? block.timestamp : startTime,
            cliffDuration: cliffDuration,
            duration: duration,
            released: 0
        }));
        beneficiarySchedules[beneficiary].push(scheduleId);

        emit ScheduleCreated(scheduleId, beneficiary, amount);
    }

    function release(uint256 scheduleId) external {
        VestingSchedule storage s = schedules[scheduleId];
        uint256 releasable = _computeReleasable(s);
        require(releasable > 0, "Nothing to release");

        s.released += releasable;
        require(token.transfer(s.beneficiary, releasable), "Transfer failed");

        emit TokensReleased(scheduleId, s.beneficiary, releasable);
    }

    function releaseAll(address beneficiary) external {
        uint256[] storage ids = beneficiarySchedules[beneficiary];
        for (uint256 i = 0; i < ids.length; i++) {
            VestingSchedule storage s = schedules[ids[i]];
            uint256 releasable = _computeReleasable(s);
            if (releasable > 0) {
                s.released += releasable;
                require(token.transfer(s.beneficiary, releasable), "Transfer failed");
                emit TokensReleased(ids[i], s.beneficiary, releasable);
            }
        }
    }

    function releasableAmount(uint256 scheduleId) external view returns (uint256) {
        return _computeReleasable(schedules[scheduleId]);
    }

    function getScheduleCount() external view returns (uint256) {
        return schedules.length;
    }

    function getBeneficiarySchedules(address beneficiary) external view returns (uint256[] memory) {
        return beneficiarySchedules[beneficiary];
    }

    function _computeReleasable(VestingSchedule storage s) private view returns (uint256) {
        if (block.timestamp < s.startTime + s.cliffDuration) {
            return 0;
        }
        if (block.timestamp >= s.startTime + s.duration) {
            return s.totalAmount - s.released;
        }
        uint256 elapsed = block.timestamp - s.startTime;
        uint256 vested = (s.totalAmount * elapsed) / s.duration;
        if (vested > s.released) {
            return vested - s.released;
        }
        return 0;
    }

    function withdrawToken(address to, uint256 amount) external onlyOwner {
        require(token.transfer(to, amount), "Transfer failed");
    }
}
