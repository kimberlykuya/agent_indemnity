// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IERC20 {
    function transfer(address to, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}

contract PerformanceBond {
    IERC20 public usdc;
    address public deployer;
    address public agent;

    uint256 public bondBalance;

    enum State { ACTIVE, CLAIM_FILED, SETTLED }
    State public state;

    event PremiumPaid(address indexed agent, uint256 amount, uint256 newBalance);
    event BondSlashed(address indexed victim, uint256 amount);
    event BondToppedUp(uint256 amount);

    modifier onlyDeployer() {
        require(msg.sender == deployer, "Not deployer");
        _;
    }

    modifier onlyActive() {
        require(state == State.ACTIVE, "Not active");
        _;
    }

    constructor(address _usdc, address _agent) {
        usdc = IERC20(_usdc);
        deployer = msg.sender;
        agent = _agent;
        state = State.ACTIVE;
    }

    function stakeBond(uint256 amount) external onlyDeployer onlyActive {
        require(usdc.transferFrom(msg.sender, address(this), amount), "transferFrom failed");
        bondBalance += amount;
        emit BondToppedUp(amount);
    }

    function topUpBond(uint256 amount) external onlyActive {
        require(msg.sender == agent || msg.sender == deployer, "Unauthorized");
        require(usdc.transferFrom(msg.sender, address(this), amount), "transferFrom failed");
        bondBalance += amount;
        emit PremiumPaid(msg.sender, amount, bondBalance);
    }

    function slashBond(address victim, uint256 payoutAmount) external onlyDeployer {
        require(state == State.ACTIVE, "Already settled");
        require(payoutAmount <= bondBalance, "Insufficient bond");
        state = State.CLAIM_FILED;
        bondBalance -= payoutAmount;
        require(usdc.transfer(victim, payoutAmount), "transfer failed");
        state = State.SETTLED;
        emit BondSlashed(victim, payoutAmount);
    }

    function getBondBalance() external view returns (uint256) {
        return bondBalance;
    }
}