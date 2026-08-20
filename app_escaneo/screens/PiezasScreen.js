import React, { useState, useEffect, useCallback } from 'react';
import { StyleSheet, Text, View, TextInput, FlatList, TouchableOpacity, ActivityIndicator } from 'react-native';
import { listarPiezas } from '../services/server';

export default function PiezasScreen({ onSeleccionar, onVolver }) {
  const [buscar, setBuscar] = useState('');
  const [piezas, setPiezas] = useState([]);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async (texto) => {
    try {
      const data = await listarPiezas(texto);
      setPiezas(Array.isArray(data) ? data : []);
    } catch (e) {
      setPiezas([]);
    }
    setCargando(false);
  }, []);

  useEffect(() => {
    cargar('');
  }, [cargar]);

  useEffect(() => {
    const timer = setTimeout(() => cargar(buscar), 300);
    return () => clearTimeout(timer);
  }, [buscar, cargar]);

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Selecciona la Pieza</Text>
      <Text style={styles.subtitulo}>Escaneaste un código nuevo. ¿A qué pieza pertenece?</Text>

      <TextInput
        style={styles.input}
        placeholder="Buscar pieza..."
        placeholderTextColor="#666"
        value={buscar}
        onChangeText={setBuscar}
        autoCorrect={false}
      />

      {cargando ? (
        <ActivityIndicator size="large" color="#00d4ff" style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={piezas}
          keyExtractor={(item) => item.codigo_pieza}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.item}
              onPress={() => onSeleccionar(item.codigo_pieza, item.descripcion)}
            >
              <Text style={styles.itemCodigo}>{item.codigo_pieza}</Text>
              {item.descripcion ? (
                <Text style={styles.itemDesc}>{item.descripcion}</Text>
              ) : null}
            </TouchableOpacity>
          )}
          style={styles.lista}
          ListEmptyComponent={
            <Text style={styles.vacio}>No se encontraron piezas</Text>
          }
        />
      )}

      <TouchableOpacity style={styles.botonVolver} onPress={onVolver}>
        <Text style={styles.botonTexto}>Volver</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a2e',
    paddingTop: 60,
    paddingHorizontal: 20,
  },
  titulo: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#00d4ff',
    textAlign: 'center',
    marginBottom: 4,
  },
  subtitulo: {
    fontSize: 13,
    color: '#888',
    textAlign: 'center',
    marginBottom: 16,
  },
  input: {
    backgroundColor: '#16213e',
    color: '#eee',
    fontSize: 16,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  lista: {
    flex: 1,
  },
  item: {
    backgroundColor: '#16213e',
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: '#0f3460',
  },
  itemCodigo: {
    color: '#00ff88',
    fontSize: 16,
    fontWeight: 'bold',
  },
  itemDesc: {
    color: '#aaa',
    fontSize: 13,
    marginTop: 2,
  },
  vacio: {
    color: '#666',
    textAlign: 'center',
    marginTop: 40,
    fontSize: 14,
  },
  botonVolver: {
    backgroundColor: '#e74c3c',
    paddingVertical: 14,
    paddingHorizontal: 40,
    borderRadius: 12,
    alignSelf: 'center',
    marginBottom: 40,
  },
  botonTexto: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
});
