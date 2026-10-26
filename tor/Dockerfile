# Ferry leaves through this Tor client. Internal only. Not a relay.
# curl is the health check: the same Tor Project check SearXNG runs before it serves.
FROM alpine:3.24.3
RUN apk add --no-cache tor curl \
    && mkdir -p /var/lib/tor \
    && chown -R tor:tor /var/lib/tor
COPY torrc /etc/tor/torrc
USER tor
EXPOSE 9050
CMD ["tor", "-f", "/etc/tor/torrc"]
