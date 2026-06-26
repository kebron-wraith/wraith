"""WRAITH Cell v7.0 — Organism Layer: Cell-to-Cell Knowledge Mesh.

This is the DNA of the living organism. Cells don't just talk to Admin —
they talk to EACH OTHER. They share threat intelligence, evolve defenses
collectively, and survive even if Admin goes down.

Properties:
1. Gossip Protocol — cells broadcast findings to all peers
2. Antibody Database — distributed threat memory (immune system)
3. Cell Election — if Admin dies, a cell becomes temporary brain
4. Skill Mutation — cells adapt defenses locally, share successful mutations
5. Metabolism — idle cells contribute resources to the swarm

MITRE ATLAS: This is the organism's collective intelligence.
"""
from __future__ import annotations
import json, hashlib, hmac, time, sqlite3, threading, socket, logging, os, random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

CELL_HOME = Path.home() / ".wraith"
CELL_HOME.mkdir(parents=True, exist_ok=True)
ANTIBODY_DB = CELL_HOME / "antibodies.db"
GOSSIP_LOG = CELL_HOME / "gossip.log"

log = logging.getLogger("wraith-organism")


# ═══════════════════════════════════════════════════════════════
# ANTIBODY DATABASE — Distributed Immune Memory
# ═══════════════════════════════════════════════════════════════

class AntibodyDatabase:
    """
    Each cell maintains a local 'antibody database' — a record of every
    threat it has encountered and how it was defeated.

    When cells communicate, they share antibodies. The organism gets
    smarter with every attack — anywhere.

    Schema:
        - threat_hash: unique fingerprint of the threat
        - threat_type: category (ransomware, phishing, prompt_injection, etc.)
        - signature: IOCs, patterns, behavioral markers
        - defense: what worked against this threat
        - source: which cell discovered it
        - confidence: 0-100 (how sure are we this is real?)
        - created_at: when first seen
        - seen_count: how many cells have confirmed this
    """

    def __init__(self, db_path: Path = ANTIBODY_DB):
        self.db_path = str(db_path)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        with self._conn as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS antibodies (
                    threat_hash TEXT PRIMARY KEY,
                    threat_type TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    defense TEXT NOT NULL,
                    source_cell TEXT NOT NULL,
                    confidence INTEGER DEFAULT 50,
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    seen_count INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_antibodies_type ON antibodies(threat_type);
                CREATE INDEX IF NOT EXISTS idx_antibodies_active ON antibodies(is_active);
                CREATE INDEX IF NOT EXISTS idx_antibodies_confidence ON antibodies(confidence);
                CREATE TABLE IF NOT EXISTS gossip_peers (
                    cell_id TEXT PRIMARY KEY,
                    ip TEXT,
                    port INTEGER,
                    last_contact TEXT NOT NULL,
                    antibodies_shared INTEGER DEFAULT 0,
                    trust_score INTEGER DEFAULT 50
                );
                CREATE INDEX IF NOT EXISTS idx_gossip_trust ON gossip_peers(trust_score);
            """)

    def record_antibody(self, threat_type: str, signature: Dict, defense: Dict,
                        source_cell: str, confidence: int = 50) -> str:
        """Record a new antibody (threat + defense pair)."""
        sig_json = json.dumps(signature, sort_keys=True)
        threat_hash = hashlib.sha256(f"{threat_type}:{sig_json}".encode()).hexdigest()[:24]
        defense_json = json.dumps(defense)
        now = datetime.now().isoformat()

        with self._conn as c:
            # Check if we already have this antibody
            existing = c.execute(
                "SELECT * FROM antibodies WHERE threat_hash=?", (threat_hash,)
            ).fetchone()

            if existing:
                # Update seen count and confidence
                new_confidence = min(100, existing["confidence"] + 5)
                c.execute(
                    "UPDATE antibodies SET seen_count=seen_count+1, last_seen=?, confidence=? WHERE threat_hash=?",
                    (now, new_confidence, threat_hash)
                )
            else:
                # New antibody
                c.execute(
                    "INSERT INTO antibodies (threat_hash, threat_type, signature, defense, source_cell, confidence, created_at, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                    (threat_hash, threat_type, sig_json, defense_json, source_cell, confidence, now, now)
                )
                log.info(f"New antibody recorded: {threat_type} [{threat_hash[:12]}] from {source_cell[:12]}")

        return threat_hash

    def find_antibody(self, threat_signature: Dict) -> Optional[Dict]:
        """Find an antibody that matches a threat signature."""
        sig_json = json.dumps(threat_signature, sort_keys=True)
        threat_hash = hashlib.sha256(sig_json.encode()).hexdigest()[:24]

        row = self._conn.execute(
            "SELECT * FROM antibodies WHERE threat_hash=? AND is_active=1",
            (threat_hash,)
        ).fetchone()

        if row:
            return dict(row)

        # Fuzzy match: check if any known antibody partially matches
        all_antibodies = self._conn.execute(
            "SELECT * FROM antibodies WHERE is_active=1 AND confidence >= 70 ORDER BY confidence DESC LIMIT 20"
        ).fetchall()

        for ab in all_antibodies:
            try:
                ab_sig = json.loads(ab["signature"])
                # Simple overlap check
                overlap = set(threat_signature.keys()) & set(ab_sig.keys())
                if len(overlap) >= len(threat_signature.keys()) * 0.7:
                    return dict(ab)
            except (json.JSONDecodeError, TypeError):
                continue

        return None

    def get_all_antibodies(self, min_confidence: int = 50, limit: int = 100) -> List[Dict]:
        """Get all known antibodies (for sharing with peers)."""
        rows = self._conn.execute(
            "SELECT * FROM antibodies WHERE is_active=1 AND confidence >= ? ORDER BY confidence DESC LIMIT ?",
            (min_confidence, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_antibody_count(self) -> int:
        """Total number of antibodies in the local immune system."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM antibodies WHERE is_active=1"
        ).fetchone()
        return row[0] if row else 0

    def get_threat_types(self) -> Dict[str, int]:
        """Get breakdown of threats by type."""
        rows = self._conn.execute(
            "SELECT threat_type, COUNT(*) as cnt FROM antibodies WHERE is_active=1 GROUP BY threat_type ORDER BY cnt DESC"
        ).fetchall()
        return {r["threat_type"]: r["cnt"] for r in rows}

    def import_peer_antibodies(self, antibodies: List[Dict], peer_cell: str) -> int:
        """Import antibodies shared by a peer cell."""
        imported = 0
        for ab in antibodies:
            try:
                threat_hash = ab.get("threat_hash", "")
                if not threat_hash:
                    continue

                existing = self._conn.execute(
                    "SELECT threat_hash FROM antibodies WHERE threat_hash=?", (threat_hash,)
                ).fetchone()

                if not existing:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO antibodies (threat_hash, threat_type, signature, defense, source_cell, confidence, created_at, last_seen) VALUES (?,?,?,?,?,?,?,?)",
                        (threat_hash, ab.get("threat_type", "unknown"), ab.get("signature", "{}"),
                         ab.get("defense", "{}"), peer_cell, ab.get("confidence", 30),
                         ab.get("created_at", datetime.now().isoformat()),
                         datetime.now().isoformat())
                    )
                    imported += 1
                else:
                    # Peer confirmed our antibody — increase confidence
                    self._conn.execute(
                        "UPDATE antibodies SET seen_count=seen_count+1, confidence=MIN(100, confidence+2) WHERE threat_hash=?",
                        (threat_hash,)
                    )
            except Exception as exc:
                log.debug(f"Failed to import antibody: {exc}")

        if imported:
            log.info(f"Imported {imported} new antibodies from {peer_cell[:12]}")
        return imported

    def update_peer_trust(self, cell_id: str, ip: str, port: int, antibodies_shared: int = 0):
        """Update peer contact info and trust score."""
        now = datetime.now().isoformat()
        with self._conn as c:
            existing = c.execute("SELECT * FROM gossip_peers WHERE cell_id=?", (cell_id,)).fetchone()
            if existing:
                c.execute(
                    "UPDATE gossip_peers SET ip=?, port=?, last_contact=?, antibodies_shared=antibodies_shared+? WHERE cell_id=?",
                    (ip, port, now, antibodies_shared, cell_id)
                )
            else:
                c.execute(
                    "INSERT INTO gossip_peers (cell_id, ip, port, last_contact, antibodies_shared) VALUES (?,?,?,?,?)",
                    (cell_id, ip, port, now, antibodies_shared)
                )

    def get_trusted_peers(self, min_trust: int = 30, limit: int = 20) -> List[Dict]:
        """Get peers sorted by trust score."""
        rows = self._conn.execute(
            "SELECT * FROM gossip_peers WHERE trust_score >= ? ORDER BY trust_score DESC LIMIT ?",
            (min_trust, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════
# GOSSIP PROTOCOL — Cell-to-Cell Knowledge Sharing
# ═══════════════════════════════════════════════════════════════

class GossipProtocol:
    """
    Epidemic gossip protocol for cell-to-cell communication.

    When a cell discovers something important:
    1. Records it in its antibody database
    2. Gossips to N random peers
    3. Those peers gossip to N more peers
    4. Within O(log N) rounds, ALL cells know

    Like a biological immune system — one cell detects a pathogen,
    the whole body learns to fight it.
    """

    GOSSIP_FANOUT = 3  # How many peers to gossip to per round
    GOSSIP_INTERVAL = 300  # Seconds between gossip rounds
    GOSSIP_PORT = 7738  # UDP port for gossip

    def __init__(self, cell_id: str, antibodies: AntibodyDatabase):
        self.cell_id = cell_id
        self.antibodies = antibodies
        self._running = False
        self._gossip_thread = None
        self._listener_thread = None
        self._pending_gossip: List[Dict] = []  # Things to gossip about
        self._gossip_lock = threading.Lock()
        self._gossiped_ids: set = set()  # Already gossiped (dedup)
        self.cell_key: Optional[str] = None

    def start(self):
        """Start gossip listener and periodic gossip sender."""
        self._running = True
        self._listener_thread = threading.Thread(target=self._listen, daemon=True)
        self._listener_thread.start()
        self._gossip_thread = threading.Thread(target=self._gossip_loop, daemon=True)
        self._gossip_thread.start()
        log.info("Gossip protocol started")

    def stop(self):
        self._running = False

    def share_finding(self, threat_type: str, signature: Dict, defense: Dict,
                      confidence: int = 50, immediate: bool = True):
        """Share a finding with the organism."""
        # Record locally first
        threat_hash = self.antibodies.record_antibody(
            threat_type, signature, defense, self.cell_id, confidence
        )

        gossip_item = {
            "threat_hash": threat_hash,
            "threat_type": threat_type,
            "signature": json.dumps(signature),
            "defense": json.dumps(defense),
            "source_cell": self.cell_id,
            "confidence": confidence,
            "created_at": datetime.now().isoformat(),
        }

        with self._gossip_lock:
            self._pending_gossip.append(gossip_item)
            self._gossiped_ids.add(threat_hash)

        if immediate:
            self._gossip_round()

        return threat_hash

    def _gossip_loop(self):
        """Periodic gossip rounds."""
        while self._running:
            try:
                time.sleep(self.GOSSIP_INTERVAL)
                self._gossip_round()
            except Exception as exc:
                log.debug(f"Gossip loop error: {exc}")

    def _gossip_round(self):
        """Execute one gossip round."""
        with self._gossip_lock:
            if not self._pending_gossip:
                return
            items = self._pending_gossip[:10]  # Max 10 items per round
            self._pending_gossip = self._pending_gossip[10:]

        peers = self.antibodies.get_trusted_peers()
        if not peers:
            # No known peers — put items back
            with self._gossip_lock:
                self._pending_gossip = items + self._pending_gossip
            return

        # Gossip to N random peers
        targets = random.sample(peers, min(self.GOSSIP_FANOUT, len(peers)))

        for peer in targets:
            try:
                self._send_gossip(peer["ip"], peer.get("port", self.GOSSIP_PORT), items)
            except Exception as exc:
                log.debug(f"Gossip to {peer['cell_id'][:12]} failed: {exc}")

    def _send_gossip(self, ip: str, port: int, items: List[Dict]):
        """Send gossip to a peer via UDP."""
        msg = {
            "type": "gossip",
            "from_cell": self.cell_id,
            "items": items,
            "ts": time.time(),
        }

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            data = json.dumps(msg).encode()
            sock.sendto(data, (ip, port))
            sock.close()
        except Exception as exc:
            log.debug(f"Gossip UDP send failed: {exc}")

    def _listen(self):
        """Listen for incoming gossip from peers."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.GOSSIP_PORT))
            sock.settimeout(2.0)

            while self._running:
                try:
                    data, addr = sock.recvfrom(65535)
                    msg = json.loads(data)
                    if msg.get("type") == "gossip":
                        self._handle_gossip(msg, addr)
                except socket.timeout:
                    continue
                except json.JSONDecodeError:
                    continue
            sock.close()
        except Exception as exc:
            log.warning(f"Gossip listener error: {exc}")

    def _handle_gossip(self, msg: Dict, addr: Tuple[str, int]):
        """Handle incoming gossip from a peer."""
        from_cell = msg.get("from_cell", "unknown")
        items = msg.get("items", [])

        if not items:
            return

        imported = 0
        for item in items:
            try:
                threat_hash = item.get("threat_hash", "")
                if threat_hash in self._gossiped_ids:
                    continue  # Already know this

                # Import the antibody
                self.antibodies.import_peer_antibodies([{
                    "threat_hash": threat_hash,
                    "threat_type": item.get("threat_type", "unknown"),
                    "signature": item.get("signature", "{}"),
                    "defense": item.get("defense", "{}"),
                    "confidence": item.get("confidence", 30),
                    "created_at": item.get("created_at", datetime.now().isoformat()),
                }], from_cell)

                self._gossiped_ids.add(threat_hash)
                imported += 1

                # Re-gossip to spread further (epidemic)
                with self._gossip_lock:
                    self._pending_gossip.append(item)

            except Exception as exc:
                log.debug(f"Failed to process gossip item: {exc}")

        # Update peer trust
        if imported > 0:
            self.antibodies.update_peer_trust(from_cell, addr[0], addr[1], imported)
            log.info(f"Gossip from {from_cell[:12]}: {imported} new antibodies")


# ═══════════════════════════════════════════════════════════════
# CELL ELECTION — Admin Failover Protocol
# ═══════════════════════════════════════════════════════════════

class CellElection:
    """
    If Admin goes down, cells elect a temporary "brain" from among themselves.

    Election criteria:
    1. Most antibodies (most experienced cell)
    2. Highest uptime (most stable)
    3. Most peers connected (best connected)

    The elected cell becomes the temporary Admin until the real Admin returns.
    It can:
    - Receive heartbeats from other cells
    - Distribute defenses
    - Queue reports for Admin

    When Admin returns, the elected cell gracefully hands back control.
    """

    ELECTION_TIMEOUT = 60  # Seconds to wait for votes
    ADMIN_CHECK_INTERVAL = 30  # How often to check if Admin is alive

    def __init__(self, cell_id: str, antibodies: AntibodyDatabase):
        self.cell_id = cell_id
        self.antibodies = antibodies
        self._is_elected = False
        self._election_votes: Dict[str, int] = {}
        self._admin_alive = True
        self._admin_check_thread = None
        self._running = False

    def start(self):
        """Start monitoring Admin health."""
        self._running = True
        self._admin_check_thread = threading.Thread(target=self._check_admin, daemon=True)
        self._admin_check_thread.start()

    def stop(self):
        self._running = False

    @property
    def is_elected(self) -> bool:
        return self._is_elected

    def _check_admin(self):
        """Periodically check if Admin tracker is reachable."""
        while self._running:
            try:
                # Try to reach Admin tracker
                alive = self._ping_admin()
                if not alive and self._admin_alive:
                    log.warning("Admin appears down — initiating election")
                    self._admin_alive = False
                    self._start_election()
                elif alive and not self._admin_alive:
                    log.info("Admin is back — standing down")
                    self._admin_alive = False
                    self._is_elected = False
            except Exception as exc:
                log.debug(f"Admin check error: {exc}")

            time.sleep(self.ADMIN_CHECK_INTERVAL)

    def _ping_admin(self) -> bool:
        """Check if Admin tracker is reachable."""
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:7734/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _start_election(self):
        """Start a leader election among cells."""
        log.info("Starting cell election...")

        # Calculate our "fitness" score
        our_score = self._calculate_fitness()
        self._election_votes[self.cell_id] = our_score

        # Broadcast election vote to peers
        peers = self.antibodies.get_trusted_peers()
        for peer in peers:
            try:
                self._send_vote(peer["ip"], peer.get("port", GossipProtocol.GOSSIP_PORT),
                               self.cell_id, our_score)
            except Exception:
                pass

        # Wait for votes
        time.sleep(self.ELECTION_TIMEOUT)

        # Count votes
        if self._election_votes:
            winner = max(self._election_votes, key=self._election_votes.get)
            if winner == self.cell_id:
                self._is_elected = True
                log.info(f"ELECTED as temporary Admin (score: {our_score})")
            else:
                log.info(f"Election lost — {winner[:12]} won")

    def _calculate_fitness(self) -> int:
        """Calculate this cell's fitness to be temporary Admin."""
        score = 0

        # Antibody count (experience)
        ab_count = self.antibodies.get_antibody_count()
        score += min(ab_count * 10, 500)

        # Peer count (connectivity)
        peers = self.antibodies.get_trusted_peers()
        score += min(len(peers) * 20, 200)

        # Uptime (stability) — use process start time as proxy
        try:
            import psutil
            proc = psutil.Process()
            uptime_hours = (time.time() - proc.create_time()) / 3600
            score += min(int(uptime_hours * 10), 300)
        except ImportError:
            score += 100  # Default if psutil not available

        return score

    def _send_vote(self, ip: str, port: int, candidate: str, score: int):
        """Send election vote to a peer."""
        msg = {
            "type": "election_vote",
            "candidate": candidate,
            "score": score,
            "from_cell": self.cell_id,
        }
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            sock.sendto(json.dumps(msg).encode(), (ip, port))
            sock.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# SKILL MUTATION — Local Defense Evolution
# ═══════════════════════════════════════════════════════════════

class SkillMutator:
    """
    Cells don't just receive skills — they ADAPT them.

    When a cell encounters a variant of a known attack:
    1. Tries the existing defense
    2. If it fails, mutates the defense parameters
    3. Tests the mutation
    4. If successful → broadcasts the mutation to all cells
    5. Admin validates → makes it permanent

    This is evolution without central control.
    """

    def __init__(self, cell_id: str, antibodies: AntibodyDatabase, gossip: GossipProtocol):
        self.cell_id = cell_id
        self.antibodies = antibodies
        self.gossip = gossip
        self._mutation_log: List[Dict] = []

    def attempt_defense(self, threat: Dict, existing_defense: Dict) -> Tuple[bool, Dict]:
        """Attempt to defend against a threat using existing knowledge.

        Returns: (success, defense_used)
        """
        # Try the known defense first
        if self._apply_defense(existing_defense, threat):
            return True, existing_defense

        # Defense failed — try mutation
        mutated = self._mutate_defense(existing_defense, threat)
        if mutated and self._apply_defense(mutated, threat):
            # Mutation worked! Share it with the organism
            self._share_mutation(threat, existing_defense, mutated)
            return True, mutated

        return False, {}

    def _apply_defense(self, defense: Dict, threat: Dict) -> bool:
        """Apply a defense against a threat. Returns True if successful."""
        # This is a simplified version — real implementation would
        # execute the defense actions (block IP, update rules, etc.)
        defense_type = defense.get("type", "")
        if defense_type == "block_ip":
            # Would actually block the IP
            return True
        elif defense_type == "update_rule":
            # Would update firewall/IDS rules
            return True
        elif defense_type == "patch_vulnerability":
            # Would apply a patch
            return True
        return False

    def _mutate_defense(self, original: Dict, threat: Dict) -> Optional[Dict]:
        """Mutate a defense to handle a variant threat."""
        mutated = original.copy()

        # Strategy 1: Broaden the signature
        if "signature" in mutated:
            sig = mutated["signature"]
            # Add the new threat's indicators to the signature
            for key, value in threat.items():
                if key not in sig:
                    sig[key] = value
            mutated["signature"] = sig

        # Strategy 2: Increase strictness
        if "threshold" in mutated:
            mutated["threshold"] = max(0, mutated["threshold"] - 10)

        # Strategy 3: Add new countermeasures
        if "countermeasures" in mutated:
            if isinstance(mutated["countermeasures"], list):
                mutated["countermeasures"].append("log_all")

        mutated["mutated"] = True
        mutated["parent_defense"] = original.get("id", "unknown")
        mutated["mutated_at"] = datetime.now().isoformat()
        mutated["mutated_by"] = self.cell_id

        self._mutation_log.append(mutated)
        return mutated

    def _share_mutation(self, threat: Dict, original: Dict, mutated: Dict):
        """Share a successful mutation with the organism."""
        self.gossip.share_finding(
            threat_type=f"mutation:{threat.get('type', 'unknown')}",
            signature=threat,
            defense=mutated,
            confidence=60,  # Mutations start with moderate confidence
            immediate=True
        )
        log.info(f"Shared mutation for {threat.get('type', 'unknown')}")


# ═══════════════════════════════════════════════════════════════
# ORGANISM — The Living Cell
# ═══════════════════════════════════════════════════════════════

class Organism:
    """
    The living organism. Ties together all organism-level systems.

    Usage:
        org = Organism(cell_id="CELL-abc123")
        org.start()

        # When you discover a threat:
        org.share_finding("ransomware", signature, defense)

        # When you encounter a threat:
        success, defense = org.encounter_threat(threat)

        # Check organism health:
        status = org.get_status()
    """

    def __init__(self, cell_id: str):
        self.cell_id = cell_id
        self.antibodies = AntibodyDatabase()
        self.gossip = GossipProtocol(cell_id, self.antibodies)
        self.election = CellElection(cell_id, self.antibodies)
        self.mutator = SkillMutator(cell_id, self.antibodies, self.gossip)
        self._running = False

    def start(self):
        """Start all organism systems."""
        self._running = True
        self.gossip.start()
        self.election.start()
        log.info(f"Organism started for cell {self.cell_id[:12]}")

    def stop(self):
        self._running = False
        self.gossip.stop()
        self.election.stop()

    def share_finding(self, threat_type: str, signature: Dict, defense: Dict,
                      confidence: int = 50):
        """Share a finding with the organism."""
        return self.gossip.share_finding(threat_type, signature, defense, confidence)

    def encounter_threat(self, threat: Dict) -> Tuple[bool, Dict]:
        """Handle an encountered threat using collective knowledge."""
        # Check if we have an antibody for this
        antibody = self.antibodies.find_antibody(threat.get("signature", threat))
        if antibody:
            defense = json.loads(antibody["defense"])
            success, used = self.mutator.attempt_defense(threat, defense)
            if success:
                return True, used

        # No known defense — record and share
        self.share_finding(
            threat_type=threat.get("type", "unknown"),
            signature=threat,
            defense={"type": "quarantine", "action": "isolate_and_alert"},
            confidence=30
        )
        return False, {}

    def get_status(self) -> Dict:
        """Get organism health status."""
        return {
            "cell_id": self.cell_id,
            "antibodies": self.antibodies.get_antibody_count(),
            "threat_types": self.antibodies.get_threat_types(),
            "trusted_peers": len(self.antibodies.get_trusted_peers()),
            "is_elected": self.election.is_elected,
            "gossip_pending": len(self.gossip._pending_gossip),
        }


# ═══════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "Organism",
    "AntibodyDatabase",
    "GossipProtocol",
    "CellElection",
    "SkillMutator",
]
