FROM ghcr.io/nvidia/openshell-community/sandboxes/openclaw:latest

USER root

# 複製 CECLAW plugin
COPY plugin/dist/ /opt/ceclaw/dist/
COPY plugin/openclaw.plugin.json /opt/ceclaw/
COPY plugin/package.json /opt/ceclaw/

# 複製啟動腳本
COPY sandbox/ceclaw-start.sh /usr/local/bin/ceclaw-start
RUN chmod +x /usr/local/bin/ceclaw-start

USER sandbox
ENTRYPOINT ["/usr/local/bin/ceclaw-start"]
