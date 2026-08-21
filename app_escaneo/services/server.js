let ws = null;
let servidorIp = '';
let onMensaje = null;
let onDesconexion = null;
let reconnectTimer = null;
let reconnectDelay = 1000;
let manualClose = false;

export { servidorIp };

const crearConexion = (ip) => {
  const url = `ws://${ip}:8000/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('Conectado al servidor');
    reconnectDelay = 1000;
    if (onMensaje) onMensaje({ tipo: '_conexion_ok' });
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
  };

  ws.onclose = () => {
    console.log('Desconectado del servidor');
    if (manualClose) return;
    if (onDesconexion) onDesconexion();
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      crearConexion(ip);
    }, reconnectDelay);
  };
};

export const connectWebSocket = (ip, callback, onDisconnect) => {
  return new Promise((resolve, reject) => {
    manualClose = false;
    servidorIp = ip;
    onMensaje = callback;
    onDesconexion = onDisconnect || null;

    crearConexion(ip);

    const checkOpen = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        clearInterval(checkOpen);
        resolve();
      }
    }, 100);

    setTimeout(() => {
      clearInterval(checkOpen);
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        reject(new Error('Timeout'));
      }
    }, 5000);
  });
};

export const disconnectWs = () => {
  manualClose = true;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
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
    }),
  });

  return response.json();
};

export const listarPiezas = async (buscar = '') => {
  if (!servidorIp) throw new Error('No conectado al servidor');
  const params = buscar ? `?buscar=${encodeURIComponent(buscar)}` : '';
  const response = await fetch(`http://${servidorIp}:8000/piezas${params}`);
  return response.json();
};

export const buscarBarra = async (codigo) => {
  if (!servidorIp) throw new Error('No conectado al servidor');
  const response = await fetch(`http://${servidorIp}:8000/barra/${encodeURIComponent(codigo)}`);
  return response.json();
};

export const asociarBarra = async (codigoBarra, codigoPieza) => {
  if (!servidorIp) throw new Error('No conectado al servidor');
  const response = await fetch(`http://${servidorIp}:8000/asociar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      codigo_barra: codigoBarra,
      codigo_pieza: codigoPieza,
    }),
  });
  return response.json();
};

export const compararFactura = async (rutaPdf) => {
  if (!servidorIp) throw new Error('No conectado al servidor');
  const response = await fetch(`http://${servidorIp}:8000/comparar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ruta: rutaPdf }),
  });
  return response.json();
};
