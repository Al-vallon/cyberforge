FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssh-server \
        sudo \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash cyber \
    && mkdir -p /home/cyber/.ssh /run/sshd \
    && ssh-keygen -A

COPY flags/user.txt /home/cyber/user.txt
COPY flags/root.txt /root/root.txt
COPY target/authorized_keys /home/cyber/.ssh/authorized_keys
COPY target/system-health.sh /usr/local/bin/system-health.sh
COPY target/sshd_lab.conf /etc/ssh/sshd_config.d/cyberforge.conf
COPY target/entrypoint.sh /entrypoint.sh

# 777 on system-health.sh is the intentional, lab-only privilege-escalation
# misconfiguration (sudo NOPASSWD + world-writable script).
RUN chown cyber:cyber /home/cyber/user.txt \
    && chmod 600 /home/cyber/user.txt \
    && chown root:root /root/root.txt \
    && chmod 600 /root/root.txt \
    && chown cyber:cyber /home/cyber/.ssh /home/cyber/.ssh/authorized_keys \
    && chmod 700 /home/cyber/.ssh \
    && chmod 600 /home/cyber/.ssh/authorized_keys \
    && chown root:root /usr/local/bin/system-health.sh \
    && chmod 777 /usr/local/bin/system-health.sh \
    && printf '%s\n' \
        'Defaults:cyber !requiretty' \
        'cyber ALL=(root) NOPASSWD: /usr/local/bin/system-health.sh' \
        > /etc/sudoers.d/cyber \
    && chmod 440 /etc/sudoers.d/cyber \
    && chmod 755 /entrypoint.sh

EXPOSE 22
ENTRYPOINT ["/entrypoint.sh"]
