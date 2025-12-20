class TokenRotator:
    def __init__(self,tokens:  list[str],start_index :int):
        self.token = tokens
        self.index = start_index
        self.used = set()

    def current(self)->str:
        return self.token[self.index]
    def next(self)->str:
        self.used.add(self.index)
        for i in range(self.index+1,len(self.token)):
            if i not in  self.index:
                self.index = i
                return self.token[self.index]
            
        self.used.clear()
        self.index = 0
        return self.token[self.index]