import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, Alert, FlatList } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import ScannerScreen from './screens/ScannerScreen';
import PiezasScreen from './screens/PiezasScreen';
import FacturasScreen from './screens/FacturasScreen';
import {
  connectWebSocket, disconnectWs, enviarEscaneo, buscarBarra, asociarBarra,
  compararFactura, limpiarScans, borrarUltimo, servidorIp,
} from './services/server';

export default function App() {
  const [conectado, setConectado] = useState(false);
  const [escaneando, setEscaneando] = useState(false);
  const [historial, setHistorial] = useState([]);
  const [stats, setStats] = useState({ codigos_unicos: 0, unidades_totales: 0 });
  const [ipServidor, setIpServidor] = useState('');

  const [busquedaPieza, setBusquedaPieza] = useState(false);
  const [codigoPendiente, setCodigoPendiente] = useState('');
  const [piezaConfirmada, setPiezaConfirmada] = useState('');

  const [resultadoComparacion, setResultadoComparacion] = useState(null);
  const [cargandoComparacion, setCargandoComparacion] = useState(false);
  const [seleccionandoFactura, setSeleccionandoFactura] = useState(false);

  useEffect(() => {
    return () => disconnectWs();
  }, []);

  const manejarMensaje = (msg) => {
    if (msg.tipo === 'confirmacion') {
      setHistorial(prev => {
        const existe = prev.find(h => h.codigo === msg.codigo);
        const entrada = {
          codigo: msg.codigo,
          cantidad: msg.cantidad_total,
          nuevo: true,
          codigo_pieza: msg.codigo_pieza || null,
          descripcion: msg.descripcion || '',
        };
        if (existe) {
          return prev.map(h =>
            h.codigo === msg.codigo ? { ...h, cantidad: msg.cantidad_total } : h
          );
        }
        return [entrada, ...prev];
      });
      setStats(prev => ({
        codigos_unicos: prev.codigos_unicos + (msg.nuevo ? 1 : 0),
        unidades_totales: prev.unidades_totales + 1,
      }));
    } else if (msg.tipo === 'conexion') {
      if (msg.estadisticas) setStats(msg.estadisticas);
      if (msg.escaneos) setHistorial(msg.escaneos);
    } else if (msg.tipo === 'estadisticas') {
      setStats(msg.estadisticas);
    } else if (msg.tipo === 'lista') {
      setHistorial(msg.escaneos);
    }
  };

  const reconectar = () => {
    setConectado(false);
    Alert.alert('Desconectado', 'Se perdio la conexion con el servidor');
  };

  const conectar = async (ip) => {
    try {
      await connectWebSocket(ip, manejarMensaje, reconectar);
      setConectado(true);
      setIpServidor(ip);
    } catch (e) {
      Alert.alert('Error', 'No se pudo conectar al servidor');
    }
  };

  const escaneado = async (codigo) => {
    try {
      await enviarEscaneo(codigo, '');
      const resultado = await buscarBarra(codigo);
      if (resultado.error) {
        setCodigoPendiente(codigo);
        setBusquedaPieza(true);
      } else {
        setPiezaConfirmada(resultado.codigo_pieza);
        setTimeout(() => setPiezaConfirmada(''), 2000);
      }
    } catch (e) {
      Alert.alert('Error', 'No se pudo enviar el escaneo');
    }
  };

  const seleccionarPieza = async (codigoPieza, descripcion) => {
    try {
      await asociarBarra(codigoPendiente, codigoPieza);
      setBusquedaPieza(false);
      setCodigoPendiente('');
      setPiezaConfirmada(codigoPieza);
      setTimeout(() => setPiezaConfirmada(''), 2000);
      setHistorial(prev => {
        const existe = prev.find(h => h.codigo === codigoPendiente);
        if (existe) {
          return prev.map(h =>
            h.codigo === codigoPendiente
              ? { ...h, codigo_pieza: codigoPieza, descripcion }
              : h
          );
        }
        return prev;
      });
    } catch (e) {
      Alert.alert('Error', 'No se pudo asociar la pieza');
    }
  };

  const reiniciar = async () => {
    Alert.alert('Reiniciar', '¿Borrar todos los escaneos?', [
      { text: 'Cancelar', style: 'cancel' },
      {
        text: 'Borrar',
        style: 'destructive',
        onPress: async () => {
          try {
            await limpiarScans();
            setHistorial([]);
            setStats({ codigos_unicos: 0, unidades_totales: 0 });
          } catch (e) {
            Alert.alert('Error', 'No se pudieron borrar los escaneos');
          }
        },
      },
    ]);
  };

  const borrarUltimoScan = async () => {
    if (historial.length === 0) {
      Alert.alert('Vacío', 'No hay escaneos para borrar.');
      return;
    }
    try {
      const resultado = await borrarUltimo();
      if (resultado.ok) {
        setHistorial(prev => prev.slice(1));
        setStats(prev => ({
          codigos_unicos: Math.max(0, prev.codigos_unicos - 1),
          unidades_totales: Math.max(0, prev.unidades_totales - 1),
        }));
      }
    } catch (e) {
      Alert.alert('Error', 'No se pudo borrar el último escaneo');
    }
  };

  const iniciarComparacion = () => {
    if (historial.length === 0) {
      Alert.alert('Sin escaneos', 'Escanea algunos productos primero.');
      return;
    }
    setSeleccionandoFactura(true);
  };

  const facturaSeleccionada = async (rutaPdf, numeroFactura) => {
    setSeleccionandoFactura(false);
    setCargandoComparacion(true);
    try {
      const resultado = await compararFactura(rutaPdf);
      if (resultado.error) {
        Alert.alert('Error', resultado.error);
        setCargandoComparacion(false);
        return;
      }
      const escaneados = {};
      historial.forEach(h => {
        const key = h.codigo_pieza || h.codigo;
        escaneados[key] = (escaneados[key] || 0) + h.cantidad;
      });
      const factura = {};
      resultado.items.forEach(it => {
        factura[it.codigo] = (factura[it.codigo] || 0) + it.cant;
      });
      const coinciden = [];
      const faltan = [];
      const sobran = [];
      Object.keys(factura).forEach(cod => {
        if (escaneados[cod]) {
          coinciden.push({ codigo: cod, factura: factura[cod], escaneado: escaneados[cod] });
        } else {
          faltan.push({ codigo: cod, factura: factura[cod] });
        }
      });
      Object.keys(escaneados).forEach(cod => {
        if (!factura[cod]) {
          sobran.push({ codigo: cod, escaneado: escaneados[cod] });
        }
      });
      setResultadoComparacion({
        factura: resultado.factura,
        coinciden,
        faltan,
        sobran,
      });
    } catch (e) {
      Alert.alert('Error', 'No se pudo comparar: ' + e.message);
    }
    setCargandoComparacion(false);
  };

  const resetearComparacion = async () => {
    try {
      await limpiarScans();
      setHistorial([]);
      setStats({ codigos_unicos: 0, unidades_totales: 0 });
    } catch (e) {
    }
    setResultadoComparacion(null);
  };

  if (busquedaPieza) {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
        <PiezasScreen
          onSeleccionar={seleccionarPieza}
          onVolver={() => { setBusquedaPieza(false); setCodigoPendiente(''); }}
        />
      </View>
    );
  }

  if (seleccionandoFactura) {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
        <FacturasScreen
          onSeleccionar={facturaSeleccionada}
          onVolver={() => setSeleccionandoFactura(false)}
        />
      </View>
    );
  }

  if (escaneando) {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
        <ScannerScreen
          onEscaneado={escaneado}
          onVolver={() => setEscaneando(false)}
          piezaActual={piezaConfirmada}
          codigoPendiente={codigoPendiente}
        />
      </View>
    );
  }

  if (!conectado) {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
        <Text style={styles.titulo}>Escaneo de Codigos</Text>
        <Text style={styles.subtitulo}>Conecta al servidor para comenzar</Text>
        <TouchableOpacity
          style={styles.botonConectar}
          onPress={() => {
            Alert.prompt(
              'IP del servidor',
              'Ingresa la IP de la laptop (ej: 192.168.1.5)',
              (ip) => { if (ip) conectar(ip); },
              'plain-text',
              servidorIp || '192.168.1.1'
            );
          }}
        >
          <Text style={styles.botonTexto}>Conectar al Servidor</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (resultadoComparacion) {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
        <Text style={styles.titulo}>Resultado</Text>
        <Text style={styles.conectado}>Factura: {resultadoComparacion.factura}</Text>

        {resultadoComparacion.coinciden.length > 0 && (
          <View style={styles.seccion}>
            <Text style={styles.seccionTitulo}>✅ Coinciden ({resultadoComparacion.coinciden.length})</Text>
            <FlatList
              data={resultadoComparacion.coinciden}
              keyExtractor={(item) => item.codigo}
              renderItem={({ item }) => (
                <View style={[styles.itemComp, styles.itemOk]}>
                  <Text style={styles.itemCompCodigo}>{item.codigo}</Text>
                  <Text style={styles.itemCompDetalle}>factura: {item.factura} | escaneado: {item.escaneado}</Text>
                </View>
              )}
              style={styles.listaComp}
            />
          </View>
        )}

        {resultadoComparacion.faltan.length > 0 && (
          <View style={styles.seccion}>
            <Text style={styles.seccionTitulo}>❌ Faltan ({resultadoComparacion.faltan.length})</Text>
            <FlatList
              data={resultadoComparacion.faltan}
              keyExtractor={(item) => item.codigo}
              renderItem={({ item }) => (
                <View style={[styles.itemComp, styles.itemFalta]}>
                  <Text style={styles.itemCompCodigo}>{item.codigo}</Text>
                  <Text style={styles.itemCompDetalle}>cant: {item.factura}</Text>
                </View>
              )}
              style={styles.listaComp}
            />
          </View>
        )}

        {resultadoComparacion.sobran.length > 0 && (
          <View style={styles.seccion}>
            <Text style={styles.seccionTitulo}>⚠️ Sobran ({resultadoComparacion.sobran.length})</Text>
            <FlatList
              data={resultadoComparacion.sobran}
              keyExtractor={(item) => item.codigo}
              renderItem={({ item }) => (
                <View style={[styles.itemComp, styles.itemSobra]}>
                  <Text style={styles.itemCompCodigo}>{item.codigo}</Text>
                  <Text style={styles.itemCompDetalle}>escaneado: {item.escaneado}</Text>
                </View>
              )}
              style={styles.listaComp}
            />
          </View>
        )}

        <TouchableOpacity style={styles.botonReset} onPress={resetearComparacion}>
          <Text style={styles.botonTexto}>Resetear</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="light" />
      <Text style={styles.titulo}>Escaneo de Codigos</Text>
      <Text style={styles.conectado}>Conectado a: {ipServidor}</Text>

      <View style={styles.statsContainer}>
        <View style={styles.statBox}>
          <Text style={styles.statNumero}>{stats.codigos_unicos}</Text>
          <Text style={styles.statLabel}>Codigos</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statNumero}>{stats.unidades_totales}</Text>
          <Text style={styles.statLabel}>Unidades</Text>
        </View>
      </View>

      <View style={styles.botonesRow}>
        <TouchableOpacity style={styles.botonEscanear} onPress={() => setEscaneando(true)}>
          <Text style={styles.botonTexto}>Escanear</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.botonComparar, cargandoComparacion && styles.botonDeshabilitado]}
          onPress={iniciarComparacion}
          disabled={cargandoComparacion}
        >
          <Text style={styles.botonTexto}>
            {cargandoComparacion ? 'Cargando...' : 'Comparar'}
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.botonesRow}>
        <TouchableOpacity style={styles.botonReiniciar} onPress={reiniciar}>
          <Text style={styles.botonTextoPeq}>Reiniciar</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.botonBorrar} onPress={borrarUltimoScan}>
          <Text style={styles.botonTextoPeq}>Borrar último</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.historialTitulo}>Ultimos escaneos:</Text>
      <FlatList
        data={historial.slice(0, 20)}
        keyExtractor={(item, idx) => `${item.codigo}-${idx}`}
        renderItem={({ item }) => (
          <View style={styles.itemHistorial}>
            <View style={styles.itemInfo}>
              <Text style={styles.itemCodigo}>
                {item.codigo_pieza || item.codigo}
              </Text>
              {item.codigo_pieza ? (
                <Text style={styles.itemBarcode}>{item.codigo}</Text>
              ) : null}
            </View>
            <Text style={styles.itemCantidad}>x{item.cantidad}</Text>
          </View>
        )}
        style={styles.lista}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    alignItems: 'center',
    paddingTop: 60,
    paddingHorizontal: 20,
  },
  titulo: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#00d4ff',
    marginBottom: 8,
  },
  subtitulo: {
    fontSize: 14,
    color: '#888',
    marginBottom: 40,
  },
  conectado: {
    fontSize: 12,
    color: '#00ff88',
    marginBottom: 20,
  },
  botonConectar: {
    backgroundColor: '#0f3460',
    paddingVertical: 16,
    paddingHorizontal: 40,
    borderRadius: 12,
    marginTop: 20,
  },
  botonesRow: {
    flexDirection: 'row',
    gap: 12,
    marginVertical: 6,
  },
  botonEscanear: {
    backgroundColor: '#00d4ff',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
  },
  botonComparar: {
    backgroundColor: '#9b59b6',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
  },
  botonReiniciar: {
    backgroundColor: '#e74c3c',
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  botonBorrar: {
    backgroundColor: '#e67e22',
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  botonDeshabilitado: {
    backgroundColor: '#666',
  },
  botonReset: {
    backgroundColor: '#e74c3c',
    paddingVertical: 16,
    paddingHorizontal: 50,
    borderRadius: 14,
    marginTop: 16,
    marginBottom: 40,
  },
  botonTexto: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  botonTextoPeq: {
    color: '#fff',
    fontSize: 13,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  statsContainer: {
    flexDirection: 'row',
    gap: 20,
    marginBottom: 10,
  },
  statBox: {
    backgroundColor: '#16213e',
    paddingVertical: 16,
    paddingHorizontal: 30,
    borderRadius: 12,
    alignItems: 'center',
    minWidth: 120,
  },
  statNumero: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#00ff88',
  },
  statLabel: {
    fontSize: 12,
    color: '#888',
    marginTop: 4,
  },
  historialTitulo: {
    fontSize: 14,
    color: '#888',
    alignSelf: 'flex-start',
    marginBottom: 8,
  },
  lista: {
    width: '100%',
  },
  itemHistorial: {
    backgroundColor: '#16213e',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 6,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  itemInfo: {
    flex: 1,
  },
  itemCodigo: {
    color: '#00ff88',
    fontSize: 15,
    fontWeight: 'bold',
  },
  itemBarcode: {
    color: '#666',
    fontSize: 11,
    marginTop: 1,
  },
  itemCantidad: {
    color: '#eee',
    fontSize: 16,
    fontWeight: 'bold',
    marginLeft: 10,
  },
  seccion: {
    width: '100%',
    marginBottom: 12,
  },
  seccionTitulo: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#eee',
    marginBottom: 6,
  },
  listaComp: {
    maxHeight: 150,
  },
  itemComp: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
    marginBottom: 4,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  itemOk: {
    backgroundColor: '#1a3a1a',
  },
  itemFalta: {
    backgroundColor: '#3a1a1a',
  },
  itemSobra: {
    backgroundColor: '#3a3a1a',
  },
  itemCompCodigo: {
    color: '#eee',
    fontSize: 13,
    fontWeight: '600',
  },
  itemCompDetalle: {
    color: '#888',
    fontSize: 11,
  },
});
