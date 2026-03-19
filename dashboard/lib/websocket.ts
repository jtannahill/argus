type MessageHandler = (data: any) => void;

export function createWebSocket(url: string, onMessage: MessageHandler) {
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout>;

  function connect() {
    ws = new WebSocket(url);
    ws.onmessage = (event) => {
      try {
        onMessage(JSON.parse(event.data));
      } catch {}
    };
    ws.onclose = () => {
      reconnectTimer = setTimeout(connect, 3000);
    };
  }

  connect();

  return {
    close: () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    },
  };
}
