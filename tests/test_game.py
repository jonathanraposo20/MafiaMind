import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app import (
    DEFENSES,
    STRATEGIES,
    apply_search_action,
    apply_strategy,
    app,
    choose_strategy,
    evaluate_state,
    minimax,
    new_game,
    public_state,
    _full_tree_nodes,
)


def unpruned_minimax(state, suspect, depth, maximizing, pending_strategy=None):
    """Reference search with the same public-information tree but no cutoffs."""
    if depth <= 0 or state.get("turn", 0) >= state.get("max_turns", 12):
        return evaluate_state(state), 1
    if maximizing:
        children = [
            unpruned_minimax(state, suspect, depth, False, strategy)
            for strategy in STRATEGIES
        ]
        return max(value for value, _ in children), 1 + sum(nodes for _, nodes in children)

    children = [
        unpruned_minimax(
            apply_search_action(state, suspect, pending_strategy, defense),
            suspect,
            depth - 1,
            True,
        )
        for defense in DEFENSES
    ]
    return min(value for value, _ in children), 1 + sum(nodes for _, nodes in children)


def test_new_game_has_one_hidden_mafia():
    game = new_game()
    assert game["mafia"] in game["suspects"]
    view = public_state(game)
    assert "mafia" not in view
    assert all("secret_role" not in s for s in view["suspects"])


def test_minimax_maximizes_and_minimizes_opposing_actions():
    game = new_game()
    value, line, metrics = minimax(
        game, "maya", 2, float("-inf"), float("inf"), True
    )
    reference_value, _ = unpruned_minimax(game, "maya", 2, True)
    assert value == reference_value
    assert line[0] in STRATEGIES
    assert line[1] in DEFENSES
    assert metrics["evaluated_nodes"] > 0


def test_alpha_beta_matches_unpruned_minimax_and_measures_pruning():
    game = new_game()
    alpha_value, _, metrics = minimax(
        game, "maya", 3, float("-inf"), float("inf"), True
    )
    plain_value, plain_nodes = unpruned_minimax(game, "maya", 3, True)
    assert alpha_value == plain_value
    assert metrics["pruned_branches"] > 0
    assert metrics["pruned_nodes"] > 0
    assert metrics["evaluated_nodes"] < plain_nodes
    assert metrics["evaluated_nodes"] + metrics["pruned_nodes"] == plain_nodes


def test_full_tree_accounting_stops_at_depth_and_turn_limit():
    terminal = new_game()
    terminal["turn"] = terminal["max_turns"]
    assert _full_tree_nodes(terminal, 5, True) == 1
    near_terminal = new_game()
    near_terminal["turn"] = near_terminal["max_turns"] - 1
    assert _full_tree_nodes(near_terminal, 2, True) == 13
    _, _, metrics = minimax(
        near_terminal, "maya", 2, float("-inf"), float("inf"), True
    )
    assert metrics["evaluated_nodes"] + metrics["pruned_nodes"] == _full_tree_nodes(
        near_terminal, 2, True
    )


def test_all_three_defensive_actions_are_part_of_the_minimizing_layer():
    game = new_game()
    children = [
        apply_search_action(game, "maya", "pressure", defense)
        for defense in DEFENSES
    ]
    assert set(DEFENSES) == {"deflect", "clarify", "counter"}
    assert len(children) == 3
    assert {child["turn"] for child in children} == {1}
    assert len({child["suspects"]["maya"]["suspicion"] for child in children}) == 3


def test_all_three_max_strategies_are_available():
    game = new_game()
    assert set(STRATEGIES) == {"rapport", "precision", "pressure"}
    value, line, _ = minimax(game, "maya", 1, float("-inf"), float("inf"), True)
    assert isinstance(value, float)
    assert line[0] in STRATEGIES


def test_evidence_affects_subsequent_evaluation_and_decision():
    game = new_game()
    enriched = copy.deepcopy(game)
    enriched["evidence"] = [
        {"suspect": "maya", "strength": 18, "label": "Verified trace"}
    ]
    enriched["suspects"]["maya"]["evidence"].append("Verified trace")
    baseline = choose_strategy(copy.deepcopy(game), "maya")
    with_evidence = choose_strategy(enriched, "maya")
    assert evaluate_state(enriched) > evaluate_state(game)
    assert with_evidence["value"] != baseline["value"]


def test_evaluation_does_not_use_hidden_mafia_assignment():
    first = new_game()
    second = copy.deepcopy(first)
    first["mafia"] = "maya"
    second["mafia"] = "viktor"
    assert evaluate_state(first) == evaluate_state(second)
    first_value, _, _ = minimax(first, "maya", 2, float("-inf"), float("inf"), True)
    second_value, _, _ = minimax(second, "maya", 2, float("-inf"), float("inf"), True)
    assert first_value == second_value


def test_evidence_and_accusation_flow():
    client = app.test_client()
    started = client.post("/api/new-game").get_json()
    sid = started["suspects"][0]["id"]
    response = client.post(
        "/api/interrogate",
        json={"game_id": started["game_id"], "suspect": sid, "question": "alibi"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["state"]["evidence"]) == 1
    assert data["state"]["last_ai"]["evaluated_nodes"] > 0
    assert data["state"]["last_ai"]["pruned_nodes"] >= 0
    assert "MAFIA" not in str(data["state"])
    result = client.post(
        "/api/accuse", json={"game_id": started["game_id"], "suspect": sid}
    )
    assert result.status_code == 200
    assert result.get_json()["state"]["role_revealed"] is True


def test_interrogation_uses_minimax_selected_strategy_and_defense():
    client = app.test_client()
    started = client.post("/api/new-game").get_json()
    response = client.post(
        "/api/interrogate",
        json={
            "game_id": started["game_id"],
            "suspect": "maya",
            "question": "detail",
        },
    )
    assert response.status_code == 200
    decision = response.get_json()["state"]["last_ai"]
    assert decision["strategy"] in STRATEGIES
    assert decision["defense"] in DEFENSES
    assert decision["evaluated_nodes"] >= 1


def test_invalid_interrogation_request_returns_400():
    client = app.test_client()
    started = client.post("/api/new-game").get_json()
    response = client.post(
        "/api/interrogate",
        json={
            "game_id": started["game_id"],
            "suspect": "not-a-suspect",
            "question": "alibi",
        },
    )
    assert response.status_code == 400


def test_interrogation_after_case_ends_returns_400():
    client = app.test_client()
    started = client.post("/api/new-game").get_json()
    accusation = client.post(
        "/api/accuse", json={"game_id": started["game_id"], "suspect": "maya"}
    )
    assert accusation.status_code == 200
    response = client.post(
        "/api/interrogate",
        json={
            "game_id": started["game_id"],
            "suspect": "maya",
            "question": "alibi",
        },
    )
    assert response.status_code == 400


def test_accusation_after_case_ends_returns_400():
    client = app.test_client()
    started = client.post("/api/new-game").get_json()
    payload = {"game_id": started["game_id"], "suspect": "maya"}
    assert client.post("/api/accuse", json=payload).status_code == 200
    assert client.post("/api/accuse", json=payload).status_code == 400


def test_hidden_mafia_is_not_exposed_before_final_accusation():
    client = app.test_client()
    started = client.post("/api/new-game").get_json()
    assert "mafia" not in started
    assert all("secret_role" not in suspect for suspect in started["suspects"])
    response = client.post(
        "/api/interrogate",
        json={
            "game_id": started["game_id"],
            "suspect": "maya",
            "question": "motive",
        },
    )
    body = response.get_json()
    assert response.status_code == 200
    assert "mafia" not in body["state"]
    assert all("secret_role" not in suspect for suspect in body["state"]["suspects"])
    assert "mafia" not in body["state"]["last_ai"]


def test_different_assignments_are_supported():
    assignments = {new_game()["mafia"] for _ in range(40)}
    assert len(assignments) >= 2
