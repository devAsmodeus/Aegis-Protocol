// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @title AegisRegistry
/// @notice On-chain registry mapping ENS subnames to agent metadata.
/// @dev The point of this contract: anyone can independently verify
///      that a Telegram or Discord bot claiming to be
///      `support.<project>.eth` is actually owned by the project's
///      wallet. The registry is intentionally minimal — no proxy, no
///      upgradeability, no external deps. Trust comes from immutable
///      bytecode plus the project owner's signing key.
///
///      Storage key is `keccak256(abi.encodePacked(ensSubname))`.
///      `get` returns a zero-struct for missing names so callers can
///      distinguish "never registered" without try/catch.
contract AegisRegistry {
    struct AgentRecord {
        address owner;
        string ensSubname;
        bytes32 kbCidHash;
        uint64 registeredAt;
        bool active;
    }

    /// @notice Emitted on a successful first-time registration or
    ///         reactivation of a previously deactivated name.
    event AgentRegistered(
        bytes32 indexed nameHash,
        address indexed owner,
        string ensSubname,
        bytes32 kbCidHash
    );

    /// @notice Emitted when the owner deactivates a record.
    event AgentDeactivated(bytes32 indexed nameHash);

    /// @notice Emitted when the owner rotates the knowledge-base CID.
    event AgentKbUpdated(bytes32 indexed nameHash, bytes32 newKbCidHash);

    /// @notice Reverts when a name is taken AND active.
    error AlreadyRegistered();

    /// @notice Reverts when caller is not the record's owner.
    error NotOwner();

    mapping(bytes32 => AgentRecord) private _records;

    /// @notice Register an agent under `ensSubname`.
    /// @dev Allowed if the slot is empty OR the existing record is
    ///      inactive (re-registration after deactivation). Reverts
    ///      `AlreadyRegistered` only when an active record exists.
    /// @param ensSubname Full subname, e.g. "support.aave.eth".
    /// @param kbCidHash sha256 of the 0G Storage CID for the agent's
    ///                  knowledge base. Hashed off-chain so this
    ///                  contract stays deps-free.
    function register(string calldata ensSubname, bytes32 kbCidHash) external {
        bytes32 nameHash = keccak256(abi.encodePacked(ensSubname));
        AgentRecord storage existing = _records[nameHash];
        if (existing.active) {
            revert AlreadyRegistered();
        }
        _records[nameHash] = AgentRecord({
            owner: msg.sender,
            ensSubname: ensSubname,
            kbCidHash: kbCidHash,
            registeredAt: uint64(block.timestamp),
            active: true
        });
        emit AgentRegistered(nameHash, msg.sender, ensSubname, kbCidHash);
    }

    /// @notice Mark the record under `ensSubname` inactive.
    /// @dev Owner-only. The record itself is preserved so historical
    ///      receipts still resolve to the original owner; only the
    ///      `active` flag flips.
    /// @param ensSubname Subname registered earlier.
    function deactivate(string calldata ensSubname) external {
        bytes32 nameHash = keccak256(abi.encodePacked(ensSubname));
        AgentRecord storage record = _records[nameHash];
        if (record.owner != msg.sender) {
            revert NotOwner();
        }
        record.active = false;
        emit AgentDeactivated(nameHash);
    }

    /// @notice Rotate the knowledge-base CID hash for an existing record.
    /// @dev Owner-only. Useful when documentation is republished.
    /// @param ensSubname Subname registered earlier.
    /// @param newKbCidHash sha256 of the new 0G Storage CID.
    function updateKb(string calldata ensSubname, bytes32 newKbCidHash) external {
        bytes32 nameHash = keccak256(abi.encodePacked(ensSubname));
        AgentRecord storage record = _records[nameHash];
        if (record.owner != msg.sender) {
            revert NotOwner();
        }
        record.kbCidHash = newKbCidHash;
        emit AgentKbUpdated(nameHash, newKbCidHash);
    }

    /// @notice Read the full record for `ensSubname`.
    /// @dev Returns the zero-struct (owner=address(0), active=false)
    ///      when the name was never registered. Callers MUST check
    ///      `record.owner != address(0)` or use `isActive`.
    /// @param ensSubname Subname to look up.
    /// @return record Full :solidity:`AgentRecord` (zero-struct on miss).
    function get(string calldata ensSubname) external view returns (AgentRecord memory record) {
        bytes32 nameHash = keccak256(abi.encodePacked(ensSubname));
        record = _records[nameHash];
    }

    /// @notice Cheap "is this name a live agent?" check.
    /// @param ensSubname Subname to look up.
    /// @return active True iff a record exists AND its `active` flag is set.
    function isActive(string calldata ensSubname) external view returns (bool active) {
        bytes32 nameHash = keccak256(abi.encodePacked(ensSubname));
        active = _records[nameHash].active;
    }
}
