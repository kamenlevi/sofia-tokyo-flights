from dataclasses import dataclass

LETTERS = {
    "3-3-3": "ABC-DEF-HJK", "3-4-3": "ABC-DEFG-HJK", "2-4-2": "AC-DEFG-HK", "2-3-2": "AC-DEF-HK",
    "2-2-2": "AC-DF-HK", "3-3": "ABC-DEF", "2-2": "AC-DF", "2-3": "AC-DEF", "1-2-1": "A-DG-K",
}


@dataclass(frozen=True)
class SeatPlan:
    groups: tuple[int, ...]
    seats: tuple[str, ...]
    windows: int
    note: str


def plan_seats(layout: str, party: int) -> SeatPlan | None:
    spec = LETTERS.get(layout)
    if spec is None:
        return None
    blocks = [list(b) for b in spec.split("-")]
    n = len(blocks)
    window_seats = {blocks[0][0], blocks[-1][-1]}

    def plan(groups, seats, note):
        return SeatPlan(groups, tuple(seats), sum(1 for s in seats if s in window_seats), note)

    # 1) Everyone in one block, window blocks first
    for i in sorted(range(n), key=lambda i: (i not in (0, n - 1), i)):
        b = blocks[i]
        if len(b) >= party:
            seats = b[:party] if i == 0 else b[-party:] if i == n - 1 else b[:party]
            return plan((party,), seats, f"all {party} together, row-mates")
    # 2) Split across one aisle, same row: prefer pairs (2+2 or 2+1), then 3+1
    splits = [(2, party - 2), (party - 1, 1)] if party == 4 else [(party - 1, 1)]
    for left_n, right_n in splits:
        for i in range(n - 1):
            left, right = blocks[i], blocks[i + 1]
            if len(left) >= left_n and len(right) >= right_n:
                seats = left[-left_n:] + right[:right_n]
                return plan((left_n, right_n), seats, f"{left_n} + {right_n} in the same row, across the aisle")
    return None
