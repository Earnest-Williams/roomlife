from roomlife.engine import apply_action, new_game

def test_determinism_basic():
    s1 = new_game()
    s2 = new_game()
    actions = ["work", "study", "eat_charity_rice", "skip_utilities", "sleep", "pay_utilities"]
    for a in actions:
        apply_action(s1, a, rng_seed=123)
        apply_action(s2, a, rng_seed=123)
    assert s1.player.money_pence == s2.player.money_pence
    assert s1.player.needs.hunger == s2.player.needs.hunger
    assert s1.world.day == s2.world.day
    assert s1.world.slice == s2.world.slice
