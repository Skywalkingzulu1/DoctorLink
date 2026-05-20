// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IT800Token {
    function transferFrom(address from, address to, uint256 value) external returns (bool);
    function transfer(address to, uint256 value) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract T800DEX {
    string public constant name = "T800-STT LP Token";
    string public constant symbol = "T800STT-LP";
    uint8 public constant decimals = 18;

    address public owner;
    IT800Token public t800;

    uint256 public totalLiquidity;
    mapping(address => uint256) public liquidity;

    uint256 public reserveT800;
    uint256 public reserveStt;

    uint256 public constant FEE_NUMERATOR = 997;
    uint256 public constant FEE_DENOMINATOR = 1000;

    event LiquidityAdded(address indexed provider, uint256 t800Amount, uint256 sttAmount);
    event LiquidityRemoved(address indexed provider, uint256 t800Amount, uint256 sttAmount);
    event Swapped(address indexed user, address indexed tokenIn, uint256 amountIn, uint256 amountOut);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    constructor(address _t800) {
        owner = msg.sender;
        t800 = IT800Token(_t800);
    }

    function addLiquidity(uint256 t800Amount) external payable {
        require(t800Amount > 0 || msg.value > 0, "Zero liquidity");
        require(t800.transferFrom(msg.sender, address(this), t800Amount), "T800 transfer failed");

        uint256 sttAmount = msg.value;

        uint256 t800Reserve = t800.balanceOf(address(this)) - t800Amount;
        uint256 sttReserve = address(this).balance - sttAmount;

        uint256 lpTokens;
        if (totalLiquidity == 0) {
            lpTokens = sqrt(t800Amount * sttAmount);
        } else {
            uint256 t800Share = (t800Amount * totalLiquidity) / t800Reserve;
            uint256 sttShare = (sttAmount * totalLiquidity) / sttReserve;
            lpTokens = t800Share < sttShare ? t800Share : sttShare;
        }

        require(lpTokens > 0, "Insufficient liquidity minted");
        liquidity[msg.sender] += lpTokens;
        totalLiquidity += lpTokens;

        reserveT800 = t800.balanceOf(address(this));
        reserveStt = address(this).balance;

        emit LiquidityAdded(msg.sender, t800Amount, sttAmount);
    }

    function removeLiquidity(uint256 lpTokens) external {
        require(lpTokens > 0 && liquidity[msg.sender] >= lpTokens, "Insufficient LP tokens");

        uint256 t800Out = (lpTokens * reserveT800) / totalLiquidity;
        uint256 sttOut = (lpTokens * reserveStt) / totalLiquidity;

        liquidity[msg.sender] -= lpTokens;
        totalLiquidity -= lpTokens;

        require(t800.transfer(msg.sender, t800Out), "T800 transfer failed");
        payable(msg.sender).transfer(sttOut);

        reserveT800 = t800.balanceOf(address(this));
        reserveStt = address(this).balance;

        emit LiquidityRemoved(msg.sender, t800Out, sttOut);
    }

    function swapT800ForStt(uint256 t800In, uint256 minSttOut) external {
        require(t800In > 0, "Zero input");
        require(t800.transferFrom(msg.sender, address(this), t800In), "T800 transfer failed");

        uint256 t800Reserve = t800.balanceOf(address(this)) - t800In;
        uint256 sttReserve = address(this).balance;

        uint256 t800InWithFee = t800In * FEE_NUMERATOR;
        uint256 sttOut = (t800InWithFee * sttReserve) / (t800Reserve * FEE_DENOMINATOR + t800InWithFee);

        require(sttOut >= minSttOut, "Slippage: insufficient STT out");
        require(sttOut < sttReserve, "Insufficient STT reserve");
        require(sttOut > 0, "Zero output");

        payable(msg.sender).transfer(sttOut);

        reserveT800 = t800.balanceOf(address(this));
        reserveStt = address(this).balance;

        emit Swapped(msg.sender, address(t800), t800In, sttOut);
    }

    function swapSttForT800(uint256 minT800Out) external payable {
        require(msg.value > 0, "Zero input");

        uint256 sttReserve = address(this).balance - msg.value;
        uint256 t800Reserve = t800.balanceOf(address(this));

        uint256 sttInWithFee = msg.value * FEE_NUMERATOR;
        uint256 t800Out = (sttInWithFee * t800Reserve) / (sttReserve * FEE_DENOMINATOR + sttInWithFee);

        require(t800Out >= minT800Out, "Slippage: insufficient T800 out");
        require(t800Out < t800Reserve, "Insufficient T800 reserve");
        require(t800Out > 0, "Zero output");

        require(t800.transfer(msg.sender, t800Out), "T800 transfer failed");

        reserveT800 = t800.balanceOf(address(this));
        reserveStt = address(this).balance;

        emit Swapped(msg.sender, address(0), msg.value, t800Out);
    }

    function getT800Price() external view returns (uint256) {
        if (reserveT800 == 0) return 0;
        return (reserveStt * 1e18) / reserveT800;
    }

    function getSttPrice() external view returns (uint256) {
        if (reserveStt == 0) return 0;
        return (reserveT800 * 1e18) / reserveStt;
    }

    function getSwapEstimate(uint256 t800In) external view returns (uint256 sttOut) {
        if (t800In == 0 || reserveT800 == 0) return 0;
        uint256 t800InWithFee = t800In * FEE_NUMERATOR;
        return (t800InWithFee * reserveStt) / (reserveT800 * FEE_DENOMINATOR + t800InWithFee);
    }

    function sqrt(uint256 x) private pure returns (uint256 y) {
        uint256 z = (x + 1) / 2;
        y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }

    receive() external payable {}
}
