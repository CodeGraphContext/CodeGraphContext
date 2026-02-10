CC ?= cc
CFLAGS ?= -Iinclude -DENABLE_STATS=1 -Wall -Wextra -std=c11
SRC := src/main.c src/util.c src/math/vec.c src/module.c
BIN := cgc_sample

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) $(SRC) -o $(BIN)

clean:
	rm -f $(BIN)

.PHONY: all clean