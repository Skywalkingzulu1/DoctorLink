// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * Callback contract for receiving Somnia Agent results.
 * Used when invoking agents that need to deliver results back to a callback.
 */
contract AgentCallback {
    struct AgentRequest {
        uint256 requestId;
        address requester;
        string purpose;
        bool completed;
        string result;
    }

    mapping(uint256 => AgentRequest) public requests;
    uint256[] public requestIds;

    event AgentResult(uint256 requestId, string result);

    function registerRequest(uint256 _requestId, string memory _purpose) external {
        requests[_requestId] = AgentRequest({
            requestId: _requestId,
            requester: msg.sender,
            purpose: _purpose,
            completed: false,
            result: ""
        });
        requestIds.push(_requestId);
    }

    function handleAgentResult(
        uint256 _requestId,
        bytes[] memory _responses,
        uint8 _status
    ) external {
        require(_status == 2, "Agent failed");
        require(requests[_requestId].requestId != 0, "Unknown request");

        string memory result = abi.decode(_responses[0], (string));
        requests[_requestId].completed = true;
        requests[_requestId].result = result;

        emit AgentResult(_requestId, result);
    }

    function getRequest(uint256 _requestId) external view returns (
        uint256 requestId,
        address requester,
        string memory purpose,
        bool completed,
        string memory result
    ) {
        AgentRequest storage r = requests[_requestId];
        return (r.requestId, r.requester, r.purpose, r.completed, r.result);
    }

    function getAllRequests() external view returns (uint256[] memory) {
        return requestIds;
    }
}
