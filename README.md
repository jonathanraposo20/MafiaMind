# MafiaMind — AI Social Deduction Game

MafiaMind is a single-player college AI mini-project built with Python Flask, HTML, CSS, and vanilla JavaScript. A hidden Mafia is placed among five student suspects. The detective must interrogate the suspects, collect evidence, compare personalities and suspicion signals, then make one final accusation.

## Problem statement and objectives

The problem is to design an offline decision-making opponent for a social-deduction game. The detective needs a strategy for choosing questions while the Mafia needs defensive responses that reduce exposure. The project demonstrates adversarial search, heuristic evaluation, rule-based NPC behavior, state tracking, and a browser-based game loop without external AI services.

## AI implementation

`app.py` contains a real Minimax search with alpha-beta pruning:

- The **detective is the maximizing player** and considers `rapport`, `precision`, and `pressure` interrogation strategies.
- The **Mafia-side MIN layer** considers `deflect`, `clarify`, and `counter` defensive responses as a simplified role-independent public-information simulation; it does not predict the actual hidden character's response.
- `minimax()` recursively explores an alternating game tree to depth 2. MAX selects a detective strategy, then MIN selects one of all three simulated defenses. The selected strategy and defense are applied exactly once at that boundary.
- `choose_strategy()` makes one search call from the current game state; it does not pre-apply a strategy or run a duplicate search.
- `evaluate_state()` scores only detective-visible information: public suspicion values, evidence strengths, the separation between the strongest suspect hypotheses, and investigation progress. It does not receive or inspect the hidden Mafia identity.
- The search uses a simplified role-independent public-information simulation. The real Mafia identity remains only in the game engine, which applies the actual hidden-role-specific outcome and validates the final accusation. Therefore, Minimax selects the best simulated defense branch; it does not claim to predict the actual hidden character's response.
- Every search returns `evaluated_nodes`, `pruned_branches` (cutoff events), and `pruned_nodes` (all nodes in skipped subtrees). The live AI Decision Analysis panel displays these as separate metrics.

### Evaluation function

```text
candidate_score[suspect] = suspicion + evidence_strength + 2 * evidence_count
strongest = max(candidate_score.values())
runner_up = second_highest(candidate_score.values())
separation = strongest - runner_up
evidence_quality = sum(strength for all public evidence)
confidence = min(30, 1.5 * evidence_quality)
progress_value = min(15, 0.75 * (turns + interrogations))
value = 1.8 * strongest + 2.5 * separation + confidence + progress_value - 0.25 * turns
```

### Pseudocode

```text
MINIMAX(state, depth, alpha, beta, maximizing):
    if depth == 0 or terminal(state):
        return EVALUATE_PUBLIC_STATE(state)
    if maximizing:                         # detective / MAX
        value = -infinity
        for strategy in detective_strategies:
            value = max(value, MINIMAX(state, depth, alpha, beta, false, strategy))
            alpha = max(alpha, value)
            if beta <= alpha: break        # cutoff event
        return value
    else:                                  # simulated Mafia-side / MIN
        value = +infinity
        for defense in mafia_defenses:
            child = APPLY_PUBLIC_ACTION(pending_strategy, defense)
            value = min(value, MINIMAX(child, depth - 1, alpha, beta, true))
            beta = min(beta, value)
            if beta <= alpha: break        # cutoff event
        return value
```

NPC answers are rule-based and personality-specific. The five personalities are analytical, dramatic, logical, empathetic, and guarded. The search does not know which profile is Mafia; it evaluates the public evidence board and suspicion hypotheses. After the player interrogates, the game engine applies the actual role-specific outcome privately, and the role is revealed only after accusation.

## Architecture

```text
mafiamind/
├── app.py                 Flask routes, game state, AI engine, scoring
├── templates/index.html   Single-page interface shell
├── static/css/style.css   Responsive dark-noir design
├── static/js/app.js       API calls and UI state management
└── tests/test_game.py     Pytest coverage for core gameplay
```

Game sessions are held in an in-memory dictionary to keep the architecture simple and offline. Roles are never sent to the browser in `public_state()` until `/api/accuse` closes the case.

## Setup

1. Install Python 3.10+ from <https://www.python.org/> and ensure **Add Python to PATH** is selected.
2. Open PowerShell in this folder:

```powershell
cd mafiamind
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

3. Open <http://127.0.0.1:5000>.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` for the current terminal, or use `.venv\Scripts\python.exe app.py` directly.

## Testing

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

The tests verify maximizing and minimizing behavior, equality with an unpruned reference search, terminal-aware node accounting, measured node reduction from pruning, the three defensive actions, evidence-sensitive decisions, valid Minimax interrogation choices, invalid and post-case requests, hidden roles, and different Mafia assignments.

## API routes

- `POST /api/new-game` — create a game.
- `GET /api/game/<game_id>` — retrieve the public state.
- `POST /api/interrogate` — submit a suspect and question (`alibi`, `motive`, `detail`, or `pressure`).
- `POST /api/accuse` — submit the final suspect and receive the reveal plus score.

## Limitations and extension ideas

This is intentionally a teaching prototype: sessions are memory-only, the strategy tree is shallow enough to observe quickly, and the accusation dialog is deliberately simple. A production version could persist games in SQLite, add a larger tree depth, record branch counts for a classroom visualization, and replace the browser prompt with a custom accusation modal.
