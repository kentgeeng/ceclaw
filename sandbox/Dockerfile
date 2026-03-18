FROM ghcr.io/nvidia/openshell-community/sandboxes/openclaw:latest
USER root
# 複製 CECLAW plugin
COPY plugin/dist/ /opt/ceclaw/dist/
COPY plugin/openclaw.plugin.json /opt/ceclaw/
COPY plugin/package.json /opt/ceclaw/
# 複製啟動腳本
COPY sandbox/ceclaw-start.sh /usr/local/bin/ceclaw-start
RUN chmod +x /usr/local/bin/ceclaw-start
# 讓 cluster IP 不走 proxy
ENV no_proxy="127.0.0.1,localhost,::1,10.43.0.0/16,10.200.0.0/16,172.17.0.0/16,host.openshell.internal"
ENV NO_PROXY="127.0.0.1,localhost,::1,10.43.0.0/16,10.200.0.0/16,172.17.0.0/16,host.openshell.internal"
USER sandbox
ENTRYPOINT ["/usr/local/bin/ceclaw-start"]
