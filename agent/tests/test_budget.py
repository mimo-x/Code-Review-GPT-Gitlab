from __future__ import annotations

import threading

from review_agent.budget import BudgetMeter, CasePool
from review_agent.config import BudgetConfig
from review_agent.policy import Usage


def test_pool_only_for_a_pooled_case_budget():
    assert CasePool.of(BudgetConfig()) is None
    assert CasePool.of(BudgetConfig(case_tokens=1000)) is None
    assert CasePool.of(BudgetConfig(sharing="pool")) is None
    assert CasePool.of(BudgetConfig(case_tokens=1000, sharing="pool")).limit == 1000


def test_concurrent_episodes_charge_one_pool_and_leave_it():
    pool = CasePool(10**9)
    keys = [f"C{index}" for index in range(8)]

    def episode(key):
        meter = pool.meter(key)
        for _ in range(1000):
            meter.charge(Usage(input_tokens=5, output_tokens=2))
        assert meter.used.total == 7000

    threads = [threading.Thread(target=episode, args=(key,)) for key in keys]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert pool.used == 8 * 7000 and pool.running == dict.fromkeys(keys, 7)
    for key in keys:
        pool.leave(key)
    assert pool.running == {} and pool.snapshot()["used"] == 8 * 7000


def test_pool_states_count_every_running_episode():
    pool = CasePool(1000)
    first, second = pool.meter("a"), pool.meter("b")
    first.charge(Usage(input_tokens=100))
    assert first.state() == "ok"
    # the other episode's next turn counts too: 400 + 3 x (100 + 300) reaches the limit
    second.charge(Usage(input_tokens=300))
    assert first.state() == "low" and (first.left, first.turns_left()) == (300, 3)
    assert first.detail() == {"pool": {"limit": 1000, "used": 400, "running": 2, "round": 400,
                                       "episode_used": 100}}
    # once it finished, only this episode's turns count
    pool.leave("b")
    assert first.state() == "ok" and first.left == 600
    pool.precharge(400)  # 800: WARN_AT of the pool
    assert first.state() == "low"
    pool.precharge(100)  # this episode's next turn would reach the limit
    assert first.state() == "out" and first.left == 100


def test_split_meter_is_its_own_budget():
    meter = BudgetMeter(1000)
    meter.charge(Usage(input_tokens=100))
    assert meter.state() == "ok" and meter.detail() == {}
    meter.charge(Usage(input_tokens=250))  # 350 + 3 x 250 passes the limit
    assert meter.state() == "low" and (meter.left, meter.turns_left()) == (650, 2)
    meter.charge(Usage(input_tokens=400))
    assert meter.state() == "out"
    assert BudgetMeter(None).state() == "ok"
