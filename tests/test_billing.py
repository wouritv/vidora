import billing


def test_usd_to_credits_and_majoration_pipeline():
    base = billing.usd_to_credits(2.5)
    final = billing.usd_to_final_credits(2.5)

    assert base == round(2.5 * billing.CREDIT_UNIT_PRICE_BY_DOLLAR, 2)
    assert final == round(base * billing.VIREEL_PRICE_MAJORATION, 2)


def test_estimate_llm_usage_cost_usd_for_known_and_unknown_provider():
    assert billing.estimate_llm_usage_cost_usd("unknown", 1000, 1000) == 0.0

    cost = billing.estimate_llm_usage_cost_usd("openai", 400000, 100000)
    assert cost == round((400000 / billing.OPEN_IA_INPUT_TOKEN_PER_DOLLAR) + (100000 / billing.OPEN_IA_OUTPUT_TOKEN_PER_DOLLAR), 6)


def test_calculate_credits_for_operation_enriches_payload():
    result = billing.calculate_credits_for_operation({"total_usd": 1.0, "foo": "bar"})

    assert result["foo"] == "bar"
    assert result["base_credits"] == billing.usd_to_credits(1.0)
    assert result["majoration_factor"] == billing.VIREEL_PRICE_MAJORATION
    assert result["final_credits"] == billing.apply_majoration(result["base_credits"])

