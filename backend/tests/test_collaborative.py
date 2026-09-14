from app.services.recommender import collaborative_scores, user_similarity


def test_similarity_ignores_how_generous_a_rater_is():
    """Pearson: agreeing on shape matters, not absolute values."""
    generous = {1: 10, 2: 9, 3: 8}
    harsh = {1: 7, 2: 6, 3: 5}          # same ordering, lower scale
    assert user_similarity(generous, harsh) > 0.95

    opposite = {1: 5, 2: 6, 3: 7}
    assert user_similarity(generous, opposite) < -0.95


def test_similarity_needs_enough_overlap():
    assert user_similarity({1: 9, 2: 8}, {1: 9, 2: 8}) is None       # only 2 shared
    assert user_similarity({1: 9, 2: 8, 3: 7}, {1: 9, 2: 8, 3: 7}) is not None


def test_recommends_what_similar_users_liked():
    rows = [
        # me
        (1, 10, 9), (1, 11, 8), (1, 12, 7),
        # a twin, who also loved game 99
        (2, 10, 9), (2, 11, 8), (2, 12, 7), (2, 99, 10),
        # someone with opposite taste who loved game 77
        (3, 10, 3), (3, 11, 4), (3, 12, 5), (3, 77, 10),
    ]
    scores = collaborative_scores(rows, user_id=1, exclude={10, 11, 12})
    assert 99 in scores
    assert 77 not in scores                       # opposite taste is ignored
    predicted, neighbours = scores[99]
    assert predicted > 0.9 and neighbours == 1


def test_no_signal_without_neighbours():
    rows = [(1, 10, 9), (1, 11, 8), (1, 12, 7)]   # nobody else has rated anything
    assert collaborative_scores(rows, user_id=1, exclude=set()) == {}
