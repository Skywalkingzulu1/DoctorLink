// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * DoctorLink Agent Sponsor Contract
 *
 * Holds a pool of STT and sponsors agent invocations on the Somnia Agentic L1.
 * Eliminates the need for a private key in .env — this contract holds the funds.
 *
 * Deployed once, funded with STT, then the backend calls invokeAgent()
 * which forwards the call to the Somnia platform contract.
 *
 * Flow:
 *   1. Operator funds this contract with STT
 *   2. Backend calls invokeAgent(agentId, payload)
 *   3. This contract calls platform.createRequest{value: deposit}(...)
 *   4. Platform runs the agent, returns rebate to this contract's receive()
 *   5. Backend can check agent results via the platform contract directly
 */

enum ConsensusType { Majority, Threshold }

enum ResponseStatus {
    None,
    Pending,
    Success,
    Failed,
    TimedOut
}

struct Response {
    address validator;
    bytes result;
    ResponseStatus status;
    uint256 receipt;
    uint256 timestamp;
    uint256 executionCost;
}

struct Request {
    uint256 id;
    address requester;
    address callbackAddress;
    bytes4 callbackSelector;
    address[] subcommittee;
    Response[] responses;
    uint256 responseCount;
    uint256 failureCount;
    uint256 threshold;
    uint256 createdAt;
    uint256 deadline;
    ResponseStatus status;
    ConsensusType consensusType;
    uint256 remainingBudget;
    uint256 perAgentBudget;
}

interface IAgentRequester {
    function createRequest(
        uint256 agentId,
        address callbackAddress,
        bytes4 callbackSelector,
        bytes calldata payload
    ) external payable returns (uint256 requestId);
    function getRequestDeposit() external view returns (uint256);
    function getRequest(uint256 requestId) external view returns (Request memory);
    function hasRequest(uint256 requestId) external view returns (bool);
}

contract DoctorLinkSponsor {
    IAgentRequester public constant platform =
        IAgentRequester(0x037Bb9C718F3f7fe5eCBDB0b600D607b52706776);

    address public owner;
    uint256 public constant SUBCOMMITTEE_SIZE = 3;

    // Per-agent prices in wei (matching Somnia docs: 0.07 / 0.03 / 0.10 STT)
    uint256 public llmAgentPrice     = 0.07 ether;     // LLM Inference
    uint256 public jsonApiPrice      = 0.03 ether;     // JSON API Request
    uint256 public parseWebsitePrice = 0.10 ether;     // LLM Parse Website

    // Track pending requests for callback
    mapping(uint256 => bool) public pendingRequests;

    event AgentInvoked(uint256 indexed requestId, uint256 indexed agentId, uint256 deposit);
    event AgentResponse(uint256 indexed requestId, ResponseStatus status, bytes result);
    event PriceUpdated(string agentType, uint256 newPrice);
    event Withdrawn(address indexed to, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    // Somnia platform agent IDs (testnet)
    uint256 public constant LLM_PLATFORM_ID    = 12847293847561029384;  // LLM Inference
    uint256 public constant JSON_PLATFORM_ID  = 12847293847561029384;  // Fallback to LLM
    uint256 public constant WEB_PLATFORM_ID   = 12847293847561029384;  // Fallback to LLM

    function invokeLLMAgent(bytes calldata payload) external onlyOwner returns (uint256) {
        return _invoke(LLM_PLATFORM_ID, payload, llmAgentPrice);
    }

    function invokeJsonApiAgent(bytes calldata payload) external onlyOwner returns (uint256) {
        return _invoke(JSON_PLATFORM_ID, payload, jsonApiPrice);
    }

    function invokeParseWebsiteAgent(bytes calldata payload) external onlyOwner returns (uint256) {
        return _invoke(WEB_PLATFORM_ID, payload, parseWebsitePrice);
    }

    // Main invoke: backend passes any agent ID, passes it through to platform
    // All agents use the same price pool since they all call the LLM on testnet.
    function invokeAgent(uint256 agentId, bytes calldata payload) external onlyOwner returns (uint256) {
        return _invoke(agentId, payload, llmAgentPrice);
    }

    function _invoke(uint256 agentId, bytes memory payload, uint256 perAgentPrice) internal returns (uint256) {
        uint256 reserve = platform.getRequestDeposit();
        uint256 reward = perAgentPrice * SUBCOMMITTEE_SIZE;
        uint256 deposit = reserve + reward;
        require(address(this).balance >= deposit, "Insufficient STT in sponsor");

        uint256 requestId = platform.createRequest{value: deposit}(
            agentId,
            address(this),
            this.handleResponse.selector,
            payload
        );
        pendingRequests[requestId] = true;
        emit AgentInvoked(requestId, agentId, deposit);
        return requestId;
    }

    function handleResponse(
        uint256 requestId,
        Response[] memory responses,
        ResponseStatus status,
        Request memory details
    ) external {
        require(msg.sender == address(platform), "Only platform");
        require(pendingRequests[requestId], "Unknown request");
        delete pendingRequests[requestId];

        bytes memory result;
        if (status == ResponseStatus.Success && responses.length > 0) {
            result = responses[0].result;
        }
        emit AgentResponse(requestId, status, result);
    }

    // Admin: update per-agent prices
    function setLLMPrice(uint256 _price) external onlyOwner { llmAgentPrice = _price; emit PriceUpdated("LLM", _price); }
    function setJsonApiPrice(uint256 _price) external onlyOwner { jsonApiPrice = _price; emit PriceUpdated("JSON", _price); }
    function setParseWebsitePrice(uint256 _price) external onlyOwner { parseWebsitePrice = _price; emit PriceUpdated("ParseWebsite", _price); }

    // Admin: withdraw unused STT
    function withdraw(address to, uint256 amount) external onlyOwner {
        require(to != address(0), "Invalid address");
        require(amount <= address(this).balance, "Insufficient balance");
        (bool sent, ) = to.call{value: amount}("");
        require(sent, "Withdraw failed");
        emit Withdrawn(to, amount);
    }

    // Admin: transfer ownership
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Invalid address");
        owner = newOwner;
    }

    // Query: sponsor balance
    function sponsorBalance() external view returns (uint256) {
        return address(this).balance;
    }

    // Query: get deposit needed for a given agent type
    function getRequiredDeposit(uint256 agentId) external view returns (uint256) {
        uint256 price;
        if (agentId == 1) price = llmAgentPrice;
        else if (agentId == 2) price = jsonApiPrice;
        else if (agentId == 3) price = parseWebsitePrice;
        else revert("Unknown agent ID");
        return platform.getRequestDeposit() + price * SUBCOMMITTEE_SIZE;
    }
}
