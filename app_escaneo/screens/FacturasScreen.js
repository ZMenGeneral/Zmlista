import React, { useState, useEffect } from 'react';
import {
  StyleSheet, Text, View, FlatList, TouchableOpacity, ActivityIndicator,
  TextInput, Alert,
} from 'react-native';
import { listarFacturas } from '../services/server';

export default function FacturasScreen({ onSeleccionar, onVolver }) {
  const [cargando, setCargando] = useState(true);
  const [facturas, setFacturas] = useState([]);
  const [error, setError] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [busquedaAplicada, setBusquedaAplicada] = useState('');
  const [seleccionadas, setSeleccionadas] = useState({});
  const [mesAbierto, setMesAbierto] = useState(null);

  const cargar = async (buscar = '') => {
    setCargando(true);
    setError('');
    try {
      const data = await listarFacturas(buscar);
      if (data.error) {
        setError(data.error);
      } else {
        setFacturas(data.facturas || []);
      }
    } catch (e) {
      setError('No se pudo conectar al servidor');
    }
    setCargando(false);
  };

  useEffect(() => {
    cargar();
  }, []);

  const cantidadSeleccionadas = Object.keys(seleccionadas).length;

  const toggleSeleccion = (pdf) => {
    setSeleccionadas(prev => {
      const next = { ...prev };
      if (next[pdf.ruta]) {
        delete next[pdf.ruta];
      } else {
        next[pdf.ruta] = pdf;
      }
      return next;
    });
  };

  const confirmarComparar = () => {
    const lista = Object.values(seleccionadas);
    if (lista.length === 0) {
      Alert.alert('Selecciona facturas', 'Marca al menos una nota para comparar.');
      return;
    }
    Alert.alert(
      'Comparar',
      `Comparar ${lista.length} nota(s) contra lo escaneado?`,
      [
        { text: 'Cancelar', style: 'cancel' },
        { text: 'Comparar', onPress: () => onSeleccionar(lista) },
      ]
    );
  };

  const agruparPorMes = (pdfs) => {
    const meses = [
      'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
      'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE',
    ];
    const grupos = {};
    pdfs.forEach(p => {
      const f = p.fecha;
      let mes = 'Sin fecha';
      // el backend envia la fecha como string (ISO 'YYYY-MM-DD' o 'dd-mm')
      if (typeof f === 'string' && f.length >= 7) {
        const partes = f.split('-').map(Number);
        let mm = null;
        if (partes.length === 3 && partes[0] > 1000) {
          mm = partes[1]; // ISO AAAA-MM-DD
        } else if (partes.length === 2) {
          mm = partes[1]; // dd-mm
        }
        if (mm && mm >= 1 && mm <= 12) {
          mes = meses[mm - 1];
        } else {
          const may = f.toUpperCase();
          const en = meses.find(m => may.includes(m));
          mes = en || 'Sin fecha';
        }
      } else if (f) {
        const may = String(f).toUpperCase();
        const en = meses.find(m => may.includes(m));
        mes = en || 'Sin fecha';
      }
      if (!grupos[mes]) grupos[mes] = [];
      grupos[mes].push(p);
    });
    const orden = Object.fromEntries(meses.map((m, i) => [m, i]));
    return Object.entries(grupos).sort(
      (a, b) => (orden[a[0]] ?? 99) - (orden[b[0]] ?? 99)
    );
  };

  const facturasAgrupadas = agruparPorMes(facturas);

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Notas de Factura</Text>
      <Text style={styles.subtitulo}>
        {busquedaAplicada ? `Buscando: ${busquedaAplicada}` : 'Todas las notas del año'}
      </Text>

      <View style={styles.buscadorRow}>
        <TextInput
          style={styles.buscador}
          placeholder="Buscar nota (ej: N12345)"
          placeholderTextColor="#888"
          value={busqueda}
          onChangeText={setBusqueda}
          onSubmitEditing={() => { setBusquedaAplicada(busqueda); cargar(busqueda); }}
          autoCapitalize="characters"
        />
        <TouchableOpacity
          style={styles.botonBuscar}
          onPress={() => { setBusquedaAplicada(busqueda); cargar(busqueda); }}
        >
          <Text style={styles.botonTexto}>Buscar</Text>
        </TouchableOpacity>
      </View>
      {busquedaAplicada ? (
        <TouchableOpacity
          style={styles.botonLimpiar}
          onPress={() => { setBusqueda(''); setBusquedaAplicada(''); cargar(''); }}
        >
          <Text style={styles.limpiarTexto}>Limpiar búsqueda</Text>
        </TouchableOpacity>
      ) : null}

      {cargando ? (
        <View style={styles.centro}>
          <ActivityIndicator size="large" color="#00d4ff" />
          <Text style={styles.vacio}>Cargando facturas...</Text>
        </View>
      ) : error ? (
        <View style={styles.centro}>
          <Text style={styles.error}>{error}</Text>
        </View>
      ) : facturas.length === 0 ? (
        <Text style={styles.vacio}>
          {busquedaAplicada ? 'No se encontraron notas con ese número' : 'No hay facturas en la ruta'}
        </Text>
      ) : (
        <FlatList
          data={facturasAgrupadas}
          keyExtractor={([mes]) => mes}
          renderItem={({ item: [mes, pdfs] }) => (
            <View style={styles_grupo.container}>
              <TouchableOpacity
                style={styles_grupo.header}
                onPress={() => setMesAbierto(mesAbierto === mes ? null : mes)}
              >
                <Text style={styles_grupo.mes}>{mes}</Text>
                <Text style={styles_grupo.conteo}>{pdfs.length} nota(s) {mesAbierto === mes ? '▼' : '▶'}</Text>
              </TouchableOpacity>
              {mesAbierto === mes && (
                <View style={styles_grupo.lista}>
                  {pdfs.map(pdf => {
                    const marcada = !!seleccionadas[pdf.ruta];
                    return (
                      <TouchableOpacity
                        key={`${pdf.ruta}-${pdf.nombre}`}
                        style={[styles_grupo.item, marcada && styles_grupo.itemSel]}
                        onPress={() => toggleSeleccion(pdf)}
                      >
                        <View style={[styles_grupo.checkbox, marcada && styles_grupo.checkboxSel]}>
                          {marcada ? <Text style={styles_grupo.check}>✓</Text> : null}
                        </View>
                        <View style={styles_grupo.info}>
                          <Text style={styles_grupo.itemNombre}>{pdf.nombre}</Text>
                          <Text style={styles_grupo.itemFecha}>{pdf.fecha || ''}</Text>
                        </View>
                        <TouchableOpacity
                          style={styles_grupo.botonVer}
                          onPress={() => onSeleccionar([pdf])}
                        >
                          <Text style={styles_grupo.botonVerTexto}>Ver</Text>
                        </TouchableOpacity>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              )}
            </View>
          )}
          style={styles.lista}
        />
      )}

      {cantidadSeleccionadas > 0 && (
        <TouchableOpacity style={styles.botonCompararMulti} onPress={confirmarComparar}>
          <Text style={styles.botonTexto}>
            Comparar {cantidadSeleccionadas} nota(s) seleccionada(s)
          </Text>
        </TouchableOpacity>
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
  centro: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 10,
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
    marginBottom: 12,
  },
  buscadorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  buscador: {
    flex: 1,
    backgroundColor: '#16213e',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    color: '#eee',
    fontSize: 15,
  },
  botonBuscar: {
    backgroundColor: '#0f3460',
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 8,
  },
  botonLimpiar: {
    alignSelf: 'flex-start',
    marginBottom: 8,
  },
  limpiarTexto: {
    color: '#00d4ff',
    fontSize: 13,
  },
  lista: {
    flex: 1,
  },
  vacio: {
    color: '#666',
    textAlign: 'center',
    marginTop: 40,
    fontSize: 14,
  },
  error: {
    color: '#e74c3c',
    textAlign: 'center',
    fontSize: 14,
  },
  botonCompararMulti: {
    backgroundColor: '#9b59b6',
    paddingVertical: 14,
    borderRadius: 12,
    marginBottom: 10,
  },
  botonVolver: {
    backgroundColor: '#e74c3c',
    paddingVertical: 14,
    paddingHorizontal: 40,
    borderRadius: 12,
    alignSelf: 'center',
    marginBottom: 40,
    marginTop: 6,
  },
  botonTexto: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
    textAlign: 'center',
  },
});

const styles_grupo = StyleSheet.create({
  container: {
    marginBottom: 8,
    backgroundColor: '#16213e',
    borderRadius: 8,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  mes: {
    color: '#00d4ff',
    fontSize: 15,
    fontWeight: 'bold',
  },
  conteo: {
    color: '#888',
    fontSize: 12,
  },
  lista: {
    paddingHorizontal: 8,
    paddingBottom: 8,
  },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0f3460',
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderRadius: 6,
    marginBottom: 4,
    gap: 10,
  },
  itemSel: {
    backgroundColor: '#1a4a4a',
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 5,
    borderWidth: 2,
    borderColor: '#888',
    justifyContent: 'center',
    alignItems: 'center',
  },
  checkboxSel: {
    backgroundColor: '#00ff88',
    borderColor: '#00ff88',
  },
  check: {
    color: '#1a1a2e',
    fontWeight: 'bold',
    fontSize: 14,
  },
  info: {
    flex: 1,
  },
  itemNombre: {
    color: '#eee',
    fontSize: 13,
  },
  itemFecha: {
    color: '#666',
    fontSize: 11,
    marginTop: 2,
  },
  botonVer: {
    backgroundColor: '#00d4ff',
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 6,
  },
  botonVerTexto: {
    color: '#1a1a2e',
    fontWeight: 'bold',
    fontSize: 12,
  },
});
