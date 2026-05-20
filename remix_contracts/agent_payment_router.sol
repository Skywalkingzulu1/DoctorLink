// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IT800Token {
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function transfer(address to, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner, address spender) external view returns (uint256);
}

interface ISomniaAgents {
    function createRequest(
        uint256 agentId,
        address callbackAddress,
        bytes4 callbackSelector,
        bytes calldata payload
    ) external payable returns (uint256 requestId);
    function getRequestDeposit() external view returns (uint256);
}

interface IAgentCallback {
    function handleAgentResult(uint256 requestId, bytes[] memory responses, uint8 status) external;
}

contract AgentPaymentRouter {
    address public owner;
    IT800Token public t800;
    ISomniaAgents public platform;
    address public callback;

    uint256 public constant STT_TO_T800_RATE = 30;
    uint256 public t800PerInvocation;
    uint256 public totalSttPool;
    uint256 public totalT800Collected;

    mapping(address => uint256) public userT800Spent;
    mapping(uint256 => address) public requestRequester;

    event AgentInvoked(
        uint256 indexed requestId,
        address indexed user,
        uint256 t800Paid,
        uint256 sttUsed,
        uint256 agentId
    );
    event SttPoolDeposited(address indexed from, uint256 amount);
    event SttPoolWithdrawn(address indexed to, uint256 amount);
    event T800Withdrawn(address indexed to, uint256 amount);
    event FeeRateUpdated(uint256 oldRate, uint256 newRate);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor(address _t800, address _platform, address _callback) {
        owner = msg.sender;
        t800 = IT800Token(_t800);
        platform = ISomniaAgents(_platform);
        callback = _callback;
        t800PerInvocation = 10 * 10**18;
    }

    function payAndInvoke(
        uint256 agentId,
        address callbackAddress,
        bytes4 callbackSelector,
        bytes calldata payload
    ) public returns (uint256 requestId) {
        uint256 deposit = platform.getRequestDeposit();
        require(address(this).balance >= deposit, "Insufficient STT pool");

        uint256 fee = t800PerInvocation;
        require(
            t800.transferFrom(msg.sender, address(this), fee),
            "T800 transfer failed"
        );

        totalT800Collected += fee;
        userT800Spent[msg.sender] += fee;

        totalSttPool -= deposit;

        requestId = platform.createRequest{value: deposit}(
            agentId,
            callbackAddress,
            callbackSelector,
            payload
        );

        requestRequester[requestId] = msg.sender;

        emit AgentInvoked(requestId, msg.sender, fee, deposit, agentId);
    }

    function payAndInvokeSimple(
        uint256 agentId,
        bytes calldata payload
    ) external returns (uint256 requestId) {
        bytes4 handleSelector = bytes4(keccak256("handleAgentResult(uint256,bytes[],uint8)"));
        return payAndInvoke(agentId, callback, handleSelector, payload);
    }

    /// @notice Pay for agent invocation with native STT instead of T800.
    /// @dev Uses internal 1 STT = 30 T800 rate to compute the STT fee equivalent.
    /// msg.value must cover: platform deposit + (t800PerInvocation / 30).
    function payWithStt(
        uint256 agentId,
        address callbackAddress,
        bytes4 callbackSelector,
        bytes calldata payload
    ) public payable returns (uint256 requestId) {
        uint256 deposit = platform.getRequestDeposit();
        uint256 sttFee = t800PerInvocation / STT_TO_T800_RATE;
        uint256 totalRequired = deposit + sttFee;
        require(msg.value >= totalRequired, "Insufficient STT");

        totalT800Collected += t800PerInvocation;
        userT800Spent[msg.sender] += t800PerInvocation;

        requestId = platform.createRequest{value: deposit}(
            agentId,
            callbackAddress,
            callbackSelector,
            payload
        );

        requestRequester[requestId] = msg.sender;

        if (msg.value > totalRequired) {
            payable(msg.sender).transfer(msg.value - totalRequired);
        }

        emit AgentInvoked(requestId, msg.sender, t800PerInvocation, deposit, agentId);
    }

    /// @notice Pay with STT using the default callback (simple version).
    function payWithSttSimple(uint256 agentId, bytes calldata payload)
        external payable returns (uint256 requestId)
    {
        bytes4 handleSelector = bytes4(keccak256("handleAgentResult(uint256,bytes[],uint8)"));
        return payWithStt(agentId, callback, handleSelector, payload);
    }

    function depositStt() external payable {
        totalSttPool += msg.value;
        emit SttPoolDeposited(msg.sender, msg.value);
    }

    function withdrawStt(address to, uint256 amount) external onlyOwner {
        require(amount <= address(this).balance, "Insufficient balance");
        totalSttPool -= amount;
        payable(to).transfer(amount);
        emit SttPoolWithdrawn(to, amount);
    }

    function withdrawT800(address to, uint256 amount) external onlyOwner {
        require(t800.transfer(to, amount), "T800 transfer failed");
        emit T800Withdrawn(to, amount);
    }

    function setT800FeeRate(uint256 newRate) external onlyOwner {
        emit FeeRateUpdated(t800PerInvocation, newRate);
        t800PerInvocation = newRate;
    }

    function getSttPoolBalance() external view returns (uint256) {
        return address(this).balance;
    }

    function getRequiredDeposit() external view returns (uint256) {
        return platform.getRequestDeposit();
    }

    receive() external payable {
        totalSttPool += msg.value;
        emit SttPoolDeposited(msg.sender, msg.value);
    }
}
