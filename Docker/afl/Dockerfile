FROM aflplusplus/aflplusplus

RUN apt update && \
	apt install tmux -y && \
	pip install libtmux && \
    pip install pyyaml

COPY ./tmux.conf /etc/tmux.conf

COPY afl-tmux.py /usr/bin/afl-tmux

COPY afl-pause /usr/bin/afl-pause

COPY afl-resume /usr/bin/afl-resume

RUN chmod +x /usr/bin/afl-tmux && \
    chmod +x /usr/bin/afl-pause && \
    chmod +x /usr/bin/afl-resume

