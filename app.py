from __future__ import annotations

import copy
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["SECRET_KEY"] = "mafiamind-local-secret"

SUSPECTS = {
    "maya": {
        "name": "Maya Chen", "initials": "MC", "role_title": "Student Journalist",
        "tagline": "Curious, incisive, impossible to intimidate.", "personality": "analytical",
        "color": "#78dce8", "bio": "Edits the campus paper and remembers every detail she hears.",
        "tell": "Corrects small inaccuracies before answering bigger questions.",
        "traits": ["Observant", "Direct", "Evidence-led"],
    },
    "leo": {
        "name": "Leo Martins", "initials": "LM", "role_title": "Drama Society Lead",
        "tagline": "Charismatic, expressive, and always performing.", "personality": "dramatic",
        "color": "#c792ea", "bio": "A natural storyteller who can turn a hallway into a stage.",
        "tell": "Uses vivid metaphors and gestures when a question gets personal.",
        "traits": ["Charismatic", "Emotional", "Persuasive"],
    },
    "nora": {
        "name": "Nora Okafor", "initials": "NO", "role_title": "Computer Science Major",
        "tagline": "Quiet, precise, and always three steps ahead.", "personality": "logical",
        "color": "#c3e88d", "bio": "Prefers clean systems, clear inputs, and verifiable outputs.",
        "tell": "Pauses to define exactly what she thinks a question means.",
        "traits": ["Precise", "Reserved", "Methodical"],
    },
    "sam": {
        "name": "Sam Rivera", "initials": "SR", "role_title": "Campus Resident Assistant",
        "tagline": "Warm, protective, and everyone’s first call.", "personality": "empathetic",
        "color": "#f78c6c", "bio": "Knows the residence halls and looks after people who feel overlooked.",
        "tell": "Answers with concern for others, even when the question is about them.",
        "traits": ["Warm", "Protective", "Community-minded"],
    },
    "viktor": {
        "name": "Viktor Hale", "initials": "VH", "role_title": "Business Club Treasurer",
        "tagline": "Polished, guarded, and allergic to loose ends.", "personality": "guarded",
        "color": "#ffcb6b", "bio": "Runs club finances and treats every conversation like a negotiation.",
        "tell": "Redirects questions toward procedure, receipts, and who else was present.",
        "traits": ["Controlled", "Ambitious", "Guarded"],
    },
}

QUESTIONS = [
    {"id": "alibi", "label": "Where were you at 10:15?", "icon": "◷", "description": "Pin down the timeline."},
    {"id": "motive", "label": "Who had a motive?", "icon": "◇", "description": "Probe alliances and resentments."},
    {"id": "detail", "label": "What did you notice?", "icon": "⌕", "description": "Ask for an observation only a witness could know."},
    {"id": "pressure", "label": "I found a contradiction.", "icon": "!", "description": "Apply pressure and watch the reaction."},
]

PERSONALITY_LINES = {
    "analytical": {
        "alibi": "I was in the archive room, indexing the paper's source notes. The access log should confirm it.",
        "motive": "Motive is not evidence. Start with who benefited from the missing keycard.",
        "detail": "The corridor light flickered twice. It was 10:17, not 10:15. I wrote it down.",
        "pressure": "That is not a contradiction. Your timeline has a two-minute gap, though.",
    },
    "dramatic": {
        "alibi": "Backstage, darling. Rehearsing the same monologue until everyone begged for silence.",
        "motive": "Everyone has a motive in a story. The question is who had the nerve to act.",
        "detail": "A shadow crossed the frosted glass. Very theatrical. Very suspicious.",
        "pressure": "A contradiction? Or a plot twist? You will need a better second act than that.",
    },
    "logical": {
        "alibi": "The lab terminal recorded my session from 10:02 through 10:31. That is the relevant interval.",
        "motive": "The strongest motive belongs to whoever needed the investigation delayed.",
        "detail": "The keypad was warm, but the handle was not. Someone used a code, not a key.",
        "pressure": "Your premise is incomplete. State which timestamp you believe conflicts.",
    },
    "empathetic": {
        "alibi": "I was checking on first-years in North Hall. They were shaken, so I stayed longer than planned.",
        "motive": "Please do not turn fear into a motive. Ask who had something to lose.",
        "detail": "I noticed someone leaving quickly, but I did not see their face. I am sorry.",
        "pressure": "I may have misspoken, but I would never put those students at risk.",
    },
    "guarded": {
        "alibi": "My records show I was balancing the club books. I have nothing else to add.",
        "motive": "Motive is cheap. Opportunity and access are what matter.",
        "detail": "I noticed the security desk was unattended. That is a staff issue, not mine.",
        "pressure": "You are making an accusation without documentation. Be precise.",
    },
}

EVIDENCE_LIBRARY = {
    "alibi": {"label": "Timeline fragment", "icon": "◷", "base": 5},
    "motive": {"label": "Motive thread", "icon": "◇", "base": 4},
    "detail": {"label": "Witness detail", "icon": "⌕", "base": 6},
    "pressure": {"label": "Pressure response", "icon": "!", "base": 7},
}

STRATEGIES = ("rapport", "precision", "pressure")
DEFENSES = ("deflect", "clarify", "counter")


def new_game() -> Dict[str, Any]:
    names = list(SUSPECTS)
    mafia = random.choice(names)
    return {
        "id": str(uuid.uuid4()), "mafia": mafia, "turn": 0, "max_turns": 12,
        "suspects": {sid: {"suspicion": 8, "interrogated": 0, "evidence": []} for sid in names},
        "evidence": [], "history": [], "ended": False, "score": 0, "last_ai": None,
    }


def public_state(game: Dict[str, Any], reveal: bool = False) -> Dict[str, Any]:
    suspects = []
    for sid, profile in SUSPECTS.items():
        stats = game["suspects"][sid]
        item = {"id": sid, **profile, "suspicion": stats["suspicion"], "interrogated": stats["interrogated"], "evidence": stats["evidence"]}
        if reveal:
            item["secret_role"] = "MAFIA" if sid == game["mafia"] else "INNOCENT"
        suspects.append(item)
    return {"game_id": game["id"], "turn": game["turn"], "max_turns": game["max_turns"], "suspects": suspects,
            "evidence": game["evidence"], "history": game["history"][-8:], "ended": game["ended"], "score": game["score"],
            "last_ai": game["last_ai"], "role_revealed": reveal}


def evaluate_state(state: Dict[str, Any]) -> float:
    """Evaluate only what the detective can observe.

    The hidden role assignment is deliberately not an input.  The heuristic
    ranks the strongest public suspect hypothesis, evidence quality, separation
    from the next hypothesis, and investigation progress.  The engine still
    keeps the real role for final accusation validation, but the search never
    reads it.
    """
    candidate_scores = {}
    for suspect, stats in state["suspects"].items():
        evidence_strength = sum(
            item["strength"]
            for item in state.get("evidence", [])
            if item.get("suspect") == suspect
        )
        candidate_scores[suspect] = (
            stats["suspicion"] + evidence_strength + len(stats["evidence"]) * 2
        )

    ranked = sorted(candidate_scores.values(), reverse=True)
    strongest = ranked[0] if ranked else 0
    runner_up = ranked[1] if len(ranked) > 1 else 0
    evidence_quality = sum(item.get("strength", 0) for item in state.get("evidence", []))
    progress = state.get("turn", 0) + sum(
        item["interrogated"] for item in state["suspects"].values()
    )
    separation = strongest - runner_up
    confidence = min(30, evidence_quality * 1.5)
    progress_value = min(15, progress * 0.75)
    return round(strongest * 1.8 + separation * 2.5 + confidence + progress_value - state.get("turn", 0) * 0.25, 3)


def apply_strategy(state: Dict[str, Any], suspect: str, strategy: str, defense: str, mafia: str) -> Dict[str, Any]:
    next_state = copy.deepcopy(state)
    stats = next_state["suspects"][suspect]
    stats["interrogated"] += 1
    is_mafia = suspect == mafia
    defense_delta = {"deflect": 0, "clarify": 1, "counter": 2}[defense]
    strategy_delta = {"rapport": 1, "precision": 3, "pressure": 5}[strategy]
    if is_mafia:
        gain = max(0, strategy_delta - defense_delta)
        stats["suspicion"] = min(100, stats["suspicion"] + gain)
        if gain >= 3:
            stats["evidence"].append(strategy)
    else:
        stats["suspicion"] = max(0, stats["suspicion"] - (1 if strategy == "rapport" else 0))
        if strategy == "pressure" and defense == "counter":
            stats["suspicion"] = min(100, stats["suspicion"] + 1)
    next_state["turn"] += 1
    return next_state


def apply_search_action(state: Dict[str, Any], suspect: str, strategy: str, defense: str) -> Dict[str, Any]:
    """Simulate a public-information action for Minimax.

    This intentionally has no role parameter.  It models how an observable
    interrogation changes suspicion and evidence regardless of who is secretly
    Mafia; the actual role-specific outcome is applied only by the game engine.
    """
    next_state = copy.deepcopy(state)
    stats = next_state["suspects"][suspect]
    stats["interrogated"] += 1
    defense_delta = {"deflect": 0, "clarify": 1, "counter": 2}[defense]
    strategy_delta = {"rapport": 1, "precision": 3, "pressure": 5}[strategy]
    observed_gain = max(0, strategy_delta - defense_delta)
    stats["suspicion"] = min(100, stats["suspicion"] + observed_gain)
    if observed_gain >= 2:
        stats["evidence"].append(f"{strategy}:{defense}")
        next_state["evidence"].append(
            {"suspect": suspect, "strength": observed_gain, "simulated": True}
        )
    next_state["turn"] += 1
    return next_state


def _new_search_metrics() -> Dict[str, int]:
    return {"evaluated_nodes": 0, "pruned_branches": 0, "pruned_nodes": 0}


def _full_tree_nodes(state: Dict[str, Any], depth: int, maximizing: bool) -> int:
    """Return complete subtree size, stopping at depth or the turn limit."""
    if depth <= 0 or state.get("turn", 0) >= state.get("max_turns", 12):
        return 1
    if maximizing:
        return 1 + len(STRATEGIES) * _full_tree_nodes(state, depth, False)
    child_state = {"turn": state.get("turn", 0) + 1, "max_turns": state.get("max_turns", 12)}
    return 1 + len(DEFENSES) * _full_tree_nodes(child_state, depth - 1, True)


def minimax(
    state: Dict[str, Any],
    suspect: str,
    depth: int,
    alpha: float,
    beta: float,
    maximizing: bool,
    metrics: Optional[Dict[str, int]] = None,
    pending_strategy: Optional[str] = None,
) -> Tuple[float, List[str], Dict[str, int]]:
    """Minimax with alpha-beta pruning.

    MAX is the detective and chooses one of STRATEGIES. MIN is the Mafia and
    responds with one of every DEFENSES option. The pending strategy is applied
    only once when MIN selects a defense, avoiding duplicate actions. The search
    uses only the public game state; no hidden role is passed to this function.
    """
    metrics = metrics if metrics is not None else _new_search_metrics()
    metrics["evaluated_nodes"] += 1
    if depth <= 0 or state.get("turn", 0) >= state.get("max_turns", 12):
        return evaluate_state(state), [], metrics

    if maximizing:
        best_value, best_line = float("-inf"), []
        for index, strategy in enumerate(STRATEGIES):
            value, line, _ = minimax(
                state, suspect, depth, alpha, beta, False, metrics, strategy
            )
            if value > best_value:
                best_value, best_line = value, [strategy] + line
            alpha = max(alpha, best_value)
            if beta <= alpha:
                metrics["pruned_branches"] += 1
                metrics["pruned_nodes"] += (len(STRATEGIES) - index - 1) * _full_tree_nodes(state, depth, False)
                break
        return best_value, best_line, metrics

    best_value, best_line = float("inf"), []
    assert pending_strategy in STRATEGIES
    for index, defense in enumerate(DEFENSES):
        child = apply_search_action(state, suspect, pending_strategy, defense)
        value, line, _ = minimax(
            child, suspect, depth - 1, alpha, beta, True, metrics
        )
        if value < best_value:
            best_value, best_line = value, [defense] + line
        beta = min(beta, best_value)
        if beta <= alpha:
            metrics["pruned_branches"] += 1
            metrics["pruned_nodes"] += (len(DEFENSES) - index - 1) * _full_tree_nodes(child, depth - 1, True)
            break
    return best_value, best_line, metrics


def choose_strategy(game: Dict[str, Any], suspect: str) -> Dict[str, Any]:
    """Run one search from the current evidence-aware game state."""
    value, line, metrics = minimax(
        game,
        suspect,
        depth=2,
        alpha=float("-inf"),
        beta=float("inf"),
        maximizing=True,
    )
    return {
        "strategy": line[0],
        "defense": line[1] if len(line) > 1 else "deflect",
        "value": round(value, 2),
        "line": line,
        "depth": 2,
        "pruning": "enabled",
        **metrics,
    }


GAMES: Dict[str, Dict[str, Any]] = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/new-game")
def api_new_game():
    game = new_game(); GAMES[game["id"]] = game
    return jsonify(public_state(game))

@app.get("/api/game/<game_id>")
def api_get_game(game_id: str):
    game = GAMES.get(game_id)
    if not game: return jsonify({"error": "Game not found"}), 404
    return jsonify(public_state(game, game["ended"]))

@app.post("/api/interrogate")
def api_interrogate():
    payload = request.get_json(silent=True) or {}
    game = GAMES.get(payload.get("game_id")); suspect = payload.get("suspect"); question = payload.get("question")
    if not game or suspect not in SUSPECTS or question not in PERSONALITY_LINES[SUSPECTS[suspect]["personality"]]:
        return jsonify({"error": "Invalid interrogation request"}), 400
    if game["ended"] or game["turn"] >= game["max_turns"]:
        return jsonify({"error": "The case is closed"}), 400
    decision = choose_strategy(game, suspect)
    strategy = decision["strategy"]
    defense = decision["defense"]
    game.update(apply_strategy(game, suspect, strategy, defense, game["mafia"]))
    stats = game["suspects"][suspect]
    evidence_def = EVIDENCE_LIBRARY[question]
    strength = evidence_def["base"] + (2 if suspect == game["mafia"] and strategy in ("precision", "pressure") else 0)
    evidence = {"id": str(uuid.uuid4()), "suspect": suspect, "label": evidence_def["label"], "icon": evidence_def["icon"], "question": question, "strength": strength, "turn": game["turn"]}
    stats["evidence"].append(evidence["label"]); game["evidence"].append(evidence)
    response = PERSONALITY_LINES[SUSPECTS[suspect]["personality"]][question]
    ai_note = (
        f"Minimax selected {strategy} (value {decision['value']}); "
        f"public-information defense simulation selected: {defense}. "
        f"Nodes: {decision['evaluated_nodes']}; cutoff events: {decision['pruned_branches']}; "
        f"skipped nodes: {decision['pruned_nodes']}."
    )
    game["last_ai"] = {**decision, "defense": defense, "suspect": suspect}
    game["history"].append({"suspect": suspect, "question": question, "response": response, "ai_note": ai_note, "turn": game["turn"]})
    return jsonify({"state": public_state(game), "response": response, "evidence": evidence, "ai_note": ai_note})

@app.post("/api/accuse")
def api_accuse():
    payload = request.get_json(silent=True) or {}; game = GAMES.get(payload.get("game_id")); accused = payload.get("suspect")
    if not game or accused not in SUSPECTS: return jsonify({"error": "Invalid accusation"}), 400
    if game["ended"]: return jsonify({"error": "The case is already closed"}), 400
    game["ended"] = True; correct = accused == game["mafia"]
    evidence_score = sum(e["strength"] for e in game["evidence"] if e["suspect"] == accused)
    game["score"] = max(0, (100 if correct else 20) + evidence_score * 3 - game["turn"] * 2)
    return jsonify({"correct": correct, "mafia": game["mafia"], "score": game["score"], "state": public_state(game, True)})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
