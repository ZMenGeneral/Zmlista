import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, Alert, FlatList } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import ScannerScreen from './screens/ScannerScreen';
import { connectWebSocket, disconnectWs, enviarEscaneo, servidorIp } from './services/server';

export default function App() {
  const [conectado, setConectado] = useState(false);
  const [escaneando, setEscaneando] = useState(false);
  const [historial, setHistorial] = useState([]);
  const [stats, setStats] = useState({ codigos_unicos: 0, unidades_totales: 0 });
  const [ipServidor, setIpServidor] = useState('');

  useEffect(() => {
    return () => disconnectWs();
  }, []);

  const conectar = async (ip) => {
    try {
      await connectWebSocket(ip, (msg) => {
        if (msg.tipo === 'confirmacion') {
          setHistorial(prev => {
            const existe = prev.find(h => h.codigo === msg.codigo);
            if (existe) {
              return prev.map(h =>
                h.codigo === msg.codigo ? { ...h, cantidad: msg.cantidad_total } : h
              );
            }
            return [{ codigo: msg.codigo, cantidad: msg.cantidad_total, nuevo: true }, ...prev];
          });
          setStats(prev => ({
            codigos_unicos: prev.codigos_unicos + (msg.nuevo ? 1 : 0),
            unidades_totales: prev.unidades_totales + 1,
          }));
        } else if (msg.tipo === 'estadisticas') {
          setStats(msg.estadisticas);
        } else if (msg.tipo === 'lista') {
          setHistorial(msg.escaneos);
        }
      });
      setConectado(true);
      setIpServidor(ip);
    } catch (e) {
      Alert.alert('Error', 'No se pudo conectar al servidor');
    }
  };

  const escaneado = async (codigo) => {
    try {
      await enviarEscaneo(codigo, '');
    } catch (e) {
      Alert.alert('Error', 'No se pudo enviar el escaneo');
    }
  };

  if (escaneando) {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
        <ScannerScreen
          onEscaneado={escaneado}
          onVolver={() => setEscaneando(false)}
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
        <StatusBar style="auto" />
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

      <TouchableOpacity
        style={styles.botonEscanear}
        onPress={() => setEscaneando(true)}
      >
        <Text style={styles.botonTexto}>Escanear</Text>
      </TouchableOpacity>

      <Text style={styles.historialTitulo}>Ultimos escaneos:</Text>
      <FlatList
        data={historial.slice(0, 20)}
        keyExtractor={(item, idx) => `${item.codigo}-${idx}`}
        renderItem={({ item }) => (
          <View style={styles.itemHistorial}>
            <Text style={styles.itemCodigo}>{item.codigo}</Text>
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
  botonEscanear: {
    backgroundColor: '#00d4ff',
    paddingVertical: 18,
    paddingHorizontal: 60,
    borderRadius: 16,
    marginVertical: 20,
  },
  botonTexto: {
    color: '#fff',
    fontSize: 20,
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
  },
  itemCodigo: {
    color: '#eee',
    fontSize: 14,
    fontWeight: '600',
  },
  itemCantidad: {
    color: '#00ff88',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
