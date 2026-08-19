let ws = null;
let servidorIp = '';
let onMensaje = null;

export { servidorIp };

export const connectWebSocket = (ip, callback) => {
  return new Promise((resolve, reject) => {
    servidorIp = ip;
    onMensaje = callback;

    const url = `ws://${ip}:8000/ws`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('Conectado al servidor');
      resolve();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (onMensaje) onMensaje(msg);
      } catch (e) {
        console.error('Error parsing mensaje:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      reject(error);
    };

    ws.onclose = () => {
      console.log('Desconectado del servidor');
    };
  });
};

export const disconnectWs = () => {
  if (ws) {
    ws.close();
    ws = null;
  }
};

export const enviarEscaneo = async (codigo, datosExtra = '') => {
  if (!servidorIp) throw new Error('No conectado al servidor');

  const response = await fetch(`http://${servidorIp}:8000/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      codigo,
      datos_extra: datosExtra,
      timestamp: new Date().toISOString(),
    }),
  });

  return response.json();
};

export const solicitarLista = () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ tipo: 'solicitar_lista' }));
  }
};

export const solicitarEstadisticas = () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ tipo: 'solicitar_estadisticas' }));
  }
};
