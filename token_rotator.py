class TokenRotator:
    """
    Vòng quay token: luôn trả về token hiện tại, nếu lỗi thì gọi next()
    để lấy token kế tiếp. Khi đã thử hết, reset vòng quay và đi tiếp.
    """

    def __init__(self, tokens: list[str], start_index: int = 0):
        if not tokens:
            raise ValueError("Danh sách token rỗng")
        self.tokens = tokens
        self.index = start_index % len(tokens)
        self.used = set()

    def current(self) -> str:
        return self.tokens[self.index]

    def next(self) -> str:
        self.used.add(self.index)

        # tìm token tiếp theo chưa dùng trong vòng hiện tại
        for step in range(1, len(self.tokens) + 1):
            candidate = (self.index + step) % len(self.tokens)
            if candidate not in self.used:
                self.index = candidate
                return self.tokens[self.index]

        # tất cả token đã được thử, reset vòng quay về đầu (index 0)
        self.used.clear()
        self.index = 0
        self.used.add(self.index)
        return self.tokens[self.index]