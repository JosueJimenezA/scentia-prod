'use client';

import React, { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, 
  Search, 
  Bookmark, 
  User as UserIcon, 
  Calendar, 
  Send, 
  Trash2, 
  Plus, 
  LogOut, 
  CloudSun, 
  MapPin,
  ShieldAlert,
  UserPlus,
  LogIn,
  Check,
  ChevronLeft,
  ChevronRight,
  Filter,
  BookmarkCheck,
  Thermometer,
  CloudRain,
  Wind,
  RefreshCw,
  Compass,
  TrendingUp,
  ArrowRight,
  Droplets,
  Mic,
  MicOff,
  Loader2
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function App() {
  // --- SESIÓN ---
  const [authMode, setAuthMode] = useState('login');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [token, setToken] = useState('');

  // Formularios Login / Registro
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ username: '', email: '', password: '', full_name: '' });
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');

  // --- NAVEGACIÓN Y APLICACIÓN ---
  const [activeTab, setActiveTab] = useState('recommendation');
  
  // --- COLECCIÓN DEL USUARIO & PAGINACIÓN ---
  const [userCollection, setUserCollection] = useState([]);
  const [userCollectionIds, setUserCollectionIds] = useState([]);
  const [collPage, setCollPage] = useState(1);
  const [collTotalPages, setCollTotalPages] = useState(1);
  const [collTotalItems, setCollTotalItems] = useState(0);
  const [isLoadingColl, setIsLoadingColl] = useState(false);

  // Filtros de colección
  const [filterStyle, setFilterStyle] = useState('');
  const [filterSeason, setFilterSeason] = useState('');
  const [filterTime, setFilterTime] = useState('');

  // --- PERFIL OLFATIVO IA ---
  const [profileData, setProfileData] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [recalculatingProfile, setRecalculatingProfile] = useState(false);
  const [profileError, setProfileError] = useState('');

  // --- BÚSQUEDA Y SCRAPING ---
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [notFoundQuery, setNotFoundQuery] = useState('');
  const [isScraping, setIsScraping] = useState(false);
  const [isScrapedResult, setIsScrapedResult] = useState(false);

  // --- AGENTE DE CLIMA Y RECOMENDACIÓN HOY ---
  const [travelInput, setTravelInput] = useState('');
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [weatherData, setWeatherData] = useState(null);
  const [weatherError, setWeatherError] = useState('');

  // --- ASISTENTE IA (AURA) CON MEMORIA Y AUDIO ---
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: 'Hola, soy Aura, tu Sommelier Olfativa Senior. ¿En qué puedo ayudarte hoy a explorar tu colección o encontrar tu próxima fragancia firma?' }
  ]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isAiReplying, setIsAiReplying] = useState(false);
  const [chatError, setChatError] = useState('');
  
  // Estados para grabación de voz con micrófono
  const [isRecording, setIsRecording] = useState(false);
  const [audioProcessing, setAudioProcessing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const chatBottomRef = useRef(null);

  // Auto-scroll al final del chat cuando entran nuevos mensajes
  useEffect(() => {
    if (activeTab === 'assistant') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, activeTab, isAiReplying]);

  // --- VERIFICAR SESIÓN ---
  useEffect(() => {
    const savedToken = localStorage.getItem('scentia_token');
    const savedUser = localStorage.getItem('scentia_user');
    if (savedToken && savedUser) {
      setToken(savedToken);
      setCurrentUser(JSON.parse(savedUser));
      setIsAuthenticated(true);
    }
  }, []);

  // Cargar IDs de la colección cuando el usuario está autenticado
  useEffect(() => {
    if (isAuthenticated && token) {
      fetchCollectionIds();
      fetchUserCollection(1);
    }
  }, [isAuthenticated, token]);

  // Cargar Perfil IA
  useEffect(() => {
    if (isAuthenticated && token && currentUser) {
      fetchUserProfile();
    }
  }, [isAuthenticated, token, currentUser]);

  // Recargar colección al cambiar filtros
  useEffect(() => {
    if (isAuthenticated && token) {
      setCollPage(1);
      fetchUserCollection(1);
    }
  }, [filterStyle, filterSeason, filterTime]);

  const fetchCollectionIds = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/collection/ids`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const ids = await res.json();
        setUserCollectionIds(ids);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchUserCollection = async (page = 1) => {
  setIsLoadingColl(true);
  try {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: '15',
      ...(filterStyle && { filterStyle }),
      ...(filterSeason && { filterSeason }),
      ...(filterTime && { filterTime })
    });

    const res = await fetch(`${API_BASE_URL}/api/v1/collection/?${params}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      const data = await res.json();
      setUserCollection(data.items);
      setCollPage(data.page);
      setCollTotalPages(data.total_pages);
      setCollTotalItems(data.total_items);
    }
  } catch (e) {
    console.error(e);
  } finally {
    setIsLoadingColl(false);
  }
};

  const handleToggleCollection = async (fragranceId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/collection/toggle/${fragranceId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        await fetchCollectionIds();
        await fetchUserCollection(collPage);
        await fetchUserProfile();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // --- CONSULTAS DEL PERFIL OLFATIVO IA ---
  const fetchUserProfile = async () => {
    if (!currentUser?.id) return;
    setLoadingProfile(true);
    setProfileError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/${currentUser.id}/ai-profile`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProfileData(data);
      } else {
        const err = await res.json();
        setProfileError(err.detail || 'No se pudo obtener el perfil olfativo.');
      }
    } catch (e) {
      console.error('Error al obtener perfil olfativo:', e);
      setProfileError('Error de conexión con el servidor.');
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleRecalculateProfile = async () => {
    if (!currentUser?.id) return;
    setRecalculatingProfile(true);
    setProfileError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/${currentUser.id}/ai-profile/recalculate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProfileData(data);
      } else {
        const err = await res.json();
        setProfileError(err.detail || 'No se pudo recalcular el perfil.');
      }
    } catch (e) {
      console.error('Error al recalcular perfil:', e);
      setProfileError('Error de conexión con el servidor.');
    } finally {
      setRecalculatingProfile(false);
    }
  };

  // --- CONSULTA AL AGENTE DE CLIMA (RECOMMENDATION_ROUTER) ---
  const handleWeatherSearch = async (e) => {
    e.preventDefault();
    if (!travelInput.trim()) return;

    setWeatherLoading(true);
    setWeatherError('');
    setWeatherData(null);

    try {
      const res = await fetch(`${API_BASE_URL}/weather/recommendation-search`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: JSON.stringify({ user_input: travelInput }),
      });

      const result = await res.json();

      if (!res.ok) {
        throw new Error(result.detail || 'No se pudo interpretar la intención o la ubicación.');
      }

      setWeatherData(result);
    } catch (err) {
      setWeatherError(err.message);
    } finally {
      setWeatherLoading(false);
    }
  };

  // --- AUTENTICACIÓN ---
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Error al iniciar sesión');

      localStorage.setItem('scentia_token', data.access_token);
      localStorage.setItem('scentia_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setCurrentUser(data.user);
      setIsAuthenticated(true);
      setLoginForm({ username: '', password: '' });
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(registerForm)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Error en el registro');

      setAuthSuccess('¡Cuenta creada con éxito! Iniciando sesión...');
      localStorage.setItem('scentia_token', data.access_token);
      localStorage.setItem('scentia_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setCurrentUser(data.user);

      setTimeout(() => {
        setIsAuthenticated(true);
        setRegisterForm({ username: '', email: '', password: '', full_name: '' });
      }, 1000);
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('scentia_token');
    localStorage.removeItem('scentia_user');
    setIsAuthenticated(false);
    setCurrentUser(null);
    setToken('');
  };

  // --- BÚSQUEDA ---
  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setNotFoundQuery('');
    setSearchResults([]);
    setIsScrapedResult(false);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/fragrances/search?q=${encodeURIComponent(searchQuery)}`);
      const data = await response.json();

      if (data.found && data.items.length > 0) {
        setSearchResults(data.items);
      } else {
        setNotFoundQuery(searchQuery);
      }
    } catch (error) {
      console.error('Error al buscar:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleTriggerScraper = async () => {
    if (!notFoundQuery) return;
    setIsScraping(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/fragrances/scrape-and-add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: notFoundQuery })
      });
      const data = await response.json();

      if (!response.ok) throw new Error(data.detail || 'No se pudo realizar el scraping');

      if (data.found && data.items.length > 0) {
        setSearchResults(data.items);
        setIsScrapedResult(true);
        setNotFoundQuery('');
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setIsScraping(false);
    }
  };

  // --- LÓGICA DEL ASISTENTE DE PERFUMERÍA (TEXTO & MICRÓFONO) ---
  const handleSendTextMessage = async (e) => {
    e?.preventDefault();
    if (!currentMessage.trim() || isAiReplying) return;

    const userText = currentMessage.trim();
    setCurrentMessage('');
    setChatError('');

    const historyPayload = chatMessages.map(msg => ({
      role: msg.role,
      content: msg.content
    }));

    setChatMessages(prev => [...prev, { role: 'user', content: userText }]);
    setIsAiReplying(true);

    try {
      const response = await fetch(`${API_BASE_URL}/perfumes/chat/text`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: JSON.stringify({
          user_input: userText,
          history: historyPayload
        })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Error al comunicarse con el asistente.');

      setChatMessages(data.updated_history);
    } catch (err) {
      setChatError(err.message);
    } finally {
      setIsAiReplying(false);
    }
  };

  const startRecording = async () => {
    setChatError('');
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());

        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        if (audioBlob.size > 0) {
          await sendAudioToBackend(audioBlob);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setChatError('No se pudo acceder al micrófono. Por favor verifica los permisos.');
      console.error('Microphone error:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const sendAudioToBackend = async (blob) => {
    setAudioProcessing(true);
    setIsAiReplying(true);
    setChatError('');

    try {
      const historyPayload = chatMessages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const formData = new FormData();
      formData.append('file', blob, 'recording.wav');
      formData.append('history_json', JSON.stringify(historyPayload));

      const response = await fetch(`${API_BASE_URL}/perfumes/chat/audio`, {
        method: 'POST',
        headers: {
          ...(token && { 'Authorization': `Bearer ${token}` })
        },
        body: formData
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Error al procesar el audio.');

      setChatMessages(data.updated_history);
    } catch (err) {
      setChatError(err.message);
    } finally {
      setAudioProcessing(false);
      setIsAiReplying(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex flex-col justify-center items-center px-4 bg-gradient-to-b from-neutral-900 via-neutral-950 to-black">
        <div className="w-full max-w-md bg-neutral-900/80 border border-amber-950/40 p-8 rounded-2xl backdrop-blur-md shadow-2xl">
          <div className="text-center mb-6">
            <span className="text-xs uppercase tracking-[0.3em] text-amber-500 font-semibold">Intelligence in Scent</span>
            <h1 className="text-4xl font-serif text-amber-100 tracking-wider mt-1">SCENTIA</h1>
            <p className="text-xs text-neutral-400 mt-2">Plataforma de Descubrimiento Olfativo</p>
          </div>

          <div className="flex border-b border-neutral-800 mb-6">
            <button
              type="button"
              onClick={() => { setAuthMode('login'); setAuthError(''); setAuthSuccess(''); }}
              className={`flex-1 py-2.5 text-xs uppercase tracking-wider font-semibold border-b-2 transition ${authMode === 'login' ? 'border-amber-500 text-amber-400' : 'border-transparent text-neutral-500'}`}
            >
              Iniciar Sesión
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode('register'); setAuthError(''); setAuthSuccess(''); }}
              className={`flex-1 py-2.5 text-xs uppercase tracking-wider font-semibold border-b-2 transition ${authMode === 'register' ? 'border-amber-500 text-amber-400' : 'border-transparent text-neutral-500'}`}
            >
              Crear Cuenta
            </button>
          </div>

          {authError && <div className="mb-4 bg-red-950/50 border border-red-800/50 text-red-300 text-xs p-3 rounded-lg flex items-center gap-2"><ShieldAlert className="w-4 h-4 shrink-0"/><span>{authError}</span></div>}
          {authSuccess && <div className="mb-4 bg-emerald-950/50 border border-emerald-800/50 text-emerald-300 text-xs p-3 rounded-lg">{authSuccess}</div>}

          {authMode === 'login' ? (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-wider text-neutral-400 mb-1">Usuario</label>
                <input type="text" value={loginForm.username} onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })} placeholder="Usuario" className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 text-neutral-100" required />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-neutral-400 mb-1">Contraseña</label>
                <input type="password" value={loginForm.password} onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })} placeholder="••••••••" className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 text-neutral-100" required />
              </div>
              <button type="submit" className="w-full bg-amber-600 hover:bg-amber-500 text-neutral-950 py-2.5 rounded-lg text-sm tracking-wider uppercase font-semibold transition flex items-center justify-center gap-2"><LogIn className="w-4 h-4"/><span>Ingresar</span></button>
            </form>
          ) : (
            <form onSubmit={handleRegisterSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-wider text-neutral-400 mb-1">Nombre Completo</label>
                <input type="text" value={registerForm.full_name} onChange={(e) => setRegisterForm({ ...registerForm, full_name: e.target.value })} placeholder="Ej. Jennifer" className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 text-neutral-100" />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-neutral-400 mb-1">Usuario</label>
                <input type="text" value={registerForm.username} onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })} placeholder="Usuario único" className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 text-neutral-100" required />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-neutral-400 mb-1">Correo Electrónico</label>
                <input type="email" value={registerForm.email} onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })} placeholder="correo@ejemplo.com" className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 text-neutral-100" required />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wider text-neutral-400 mb-1">Contraseña</label>
                <input type="password" value={registerForm.password} onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })} placeholder="••••••••" className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 text-neutral-100" required />
              </div>
              <button type="submit" className="w-full bg-amber-600 hover:bg-amber-500 text-neutral-950 py-2.5 rounded-lg text-sm tracking-wider uppercase font-semibold transition flex items-center justify-center gap-2"><UserPlus className="w-4 h-4"/><span>Registrar Cuenta</span></button>
            </form>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-neutral-950">
      <header className="border-b border-neutral-800/80 bg-neutral-900/60 sticky top-0 z-50 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-amber-700 to-amber-500 flex items-center justify-center font-serif text-lg font-bold text-neutral-950 shadow-md">S</div>
            <div>
              <h1 className="text-xl font-serif tracking-widest text-neutral-100">SCENTIA</h1>
              <p className="text-[10px] tracking-widest uppercase text-amber-500/80 -mt-1">Private Reserve</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-neutral-900 border border-neutral-800 rounded-full text-xs text-neutral-300">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span>{currentUser?.full_name || currentUser?.username}</span>
            </div>
            <button onClick={handleLogout} className="p-2 text-neutral-400 hover:text-red-400 hover:bg-neutral-900 rounded-lg transition" title="Cerrar Sesión"><LogOut className="w-5 h-5"/></button>
          </div>
        </div>
      </header>

      <div className="flex-1 max-w-7xl w-full mx-auto px-4 py-6 flex flex-col md:flex-row gap-6">
        <nav className="md:w-64 flex-shrink-0 flex md:flex-col overflow-x-auto gap-1 border-b md:border-b-0 md:border-r border-neutral-800 pb-2 md:pb-0 md:pr-4">
          <button onClick={() => setActiveTab('recommendation')} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-xs uppercase tracking-wider font-medium transition text-left whitespace-nowrap ${activeTab === 'recommendation' ? 'bg-amber-950/40 text-amber-400 border border-amber-800/40' : 'text-neutral-400 hover:bg-neutral-900'}`}><CloudSun className="w-4 h-4"/><span>Recomendación Hoy</span></button>
          <button onClick={() => setActiveTab('collection')} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-xs uppercase tracking-wider font-medium transition text-left whitespace-nowrap ${activeTab === 'collection' ? 'bg-amber-950/40 text-amber-400 border border-amber-800/40' : 'text-neutral-400 hover:bg-neutral-900'}`}><Bookmark className="w-4 h-4"/><span>Mi Colección ({collTotalItems})</span></button>
          <button onClick={() => setActiveTab('search')} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-xs uppercase tracking-wider font-medium transition text-left whitespace-nowrap ${activeTab === 'search' ? 'bg-amber-950/40 text-amber-400 border border-amber-800/40' : 'text-neutral-400 hover:bg-neutral-900'}`}><Search className="w-4 h-4"/><span>Búsqueda y Catálogo</span></button>
          <button onClick={() => setActiveTab('profile')} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-xs uppercase tracking-wider font-medium transition text-left whitespace-nowrap ${activeTab === 'profile' ? 'bg-amber-950/40 text-amber-400 border border-amber-800/40' : 'text-neutral-400 hover:bg-neutral-900'}`}><UserIcon className="w-4 h-4"/><span>Perfil Olfativo IA</span></button>
          <button onClick={() => setActiveTab('assistant')} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-xs uppercase tracking-wider font-medium transition text-left whitespace-nowrap ${activeTab === 'assistant' ? 'bg-amber-950/40 text-amber-400 border border-amber-800/40' : 'text-neutral-400 hover:bg-neutral-900'}`}><Sparkles className="w-4 h-4"/><span>Asistente IA</span></button>
        </nav>

        <main className="flex-1">
          {/* TAB: RECOMENDACIÓN HOY */}
          {activeTab === 'recommendation' && (
            <div className="bg-gradient-to-r from-neutral-900 via-neutral-900 to-neutral-950 border border-amber-900/30 p-6 rounded-2xl space-y-6">
              <div>
                <h2 className="text-2xl font-serif text-neutral-100 mb-1">Sugerencia Diaria por Clima</h2>
                <p className="text-xs text-neutral-400">Recomendaciones dinámicas calculadas por el motor meteorológico y clustering en tiempo real.</p>
              </div>

              <div className="bg-neutral-950/60 border border-neutral-800/80 rounded-xl p-5 backdrop-blur-sm">
                <label htmlFor="travel-input" className="block text-xs font-medium text-amber-200/90 mb-2">
                  ¿A dónde irás hoy o esta semana?
                </label>
                
                <form onSubmit={handleWeatherSearch} className="flex flex-col sm:flex-row gap-3">
                  <input
                    id="travel-input"
                    type="text"
                    value={travelInput}
                    onChange={(e) => setTravelInput(e.target.value)}
                    placeholder="Ej. Iré a Toluca, Estado de México el próximo lunes..."
                    className="flex-1 bg-neutral-900 border border-neutral-800 text-neutral-200 text-xs rounded-xl px-4 py-3 focus:outline-none focus:border-amber-600 transition placeholder:text-neutral-600"
                  />
                  <button
                    type="submit"
                    disabled={weatherLoading}
                    className="bg-amber-600 hover:bg-amber-500 text-neutral-950 text-xs font-semibold px-5 py-3 rounded-xl transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 whitespace-nowrap cursor-pointer"
                  >
                    {weatherLoading ? (
                      <>
                        <span className="w-3 h-3 border-2 border-neutral-950/30 border-t-neutral-950 rounded-full animate-spin" />
                        <span>Analizando...</span>
                      </>
                    ) : (
                      <>
                        <CloudSun className="w-4 h-4" />
                        <span>Consultar Clima</span>
                      </>
                    )}
                  </button>
                </form>

                {weatherError && (
                  <div className="mt-3 p-3 bg-red-950/40 border border-red-800/50 text-red-300 text-xs rounded-xl flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                    <span>{weatherError}</span>
                  </div>
                )}
              </div>

              {weatherData && (
                <div className="space-y-6">
                  {/* Tarjeta con los datos del Clima */}
                  <div className="bg-neutral-950/80 border border-amber-900/20 rounded-xl p-5 space-y-4">
                    <div className="flex items-start justify-between border-b border-neutral-800 pb-3">
                      <div>
                        <span className="text-[10px] font-semibold text-amber-500 uppercase tracking-wider flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          Ubicación
                        </span>
                        <h3 className="text-base font-serif text-neutral-100 mt-0.5">
                          {weatherData.location?.formatted_name || weatherData.location?.name || `${weatherData.location?.latitude}, ${weatherData.location?.longitude}`}
                        </h3>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] text-neutral-500 block">Fecha Objetivo</span>
                        <span className="text-xs text-amber-200 font-mono">
                          {weatherData.parsed_intent?.target_date || weatherData.forecast?.date || 'Hoy / Pronóstico cercano'}
                        </span>
                      </div>
                    </div>

                    {weatherData.forecast && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-neutral-900/60 border border-neutral-800/60 p-3 rounded-xl text-center">
                          <span className="text-[10px] text-neutral-400 uppercase flex items-center justify-center gap-1">
                            <Thermometer className="w-3 h-3 text-amber-500" /> Temp. Máx
                          </span>
                          <span className="text-sm font-bold text-amber-100 mt-1 block">
                            {weatherData.forecast.temp_max} °C
                          </span>
                        </div>

                        <div className="bg-neutral-900/60 border border-neutral-800/60 p-3 rounded-xl text-center">
                          <span className="text-[10px] text-neutral-400 uppercase flex items-center justify-center gap-1">
                            <Thermometer className="w-3 h-3 text-blue-400" /> Temp. Mín
                          </span>
                          <span className="text-sm font-bold text-amber-100 mt-1 block">
                            {weatherData.forecast.temp_min} °C
                          </span>
                        </div>

                        <div className="bg-neutral-900/60 border border-neutral-800/60 p-3 rounded-xl text-center">
                          <span className="text-[10px] text-neutral-400 uppercase flex items-center justify-center gap-1">
                            <CloudRain className="w-3 h-3 text-sky-400" /> Precipitación
                          </span>
                          <span className="text-sm font-bold text-amber-100 mt-1 block">
                            {weatherData.forecast.precipitation_sum} mm
                          </span>
                        </div>

                        <div className="bg-neutral-900/60 border border-neutral-800/60 p-3 rounded-xl text-center">
                          <span className="text-[10px] text-neutral-400 uppercase flex items-center justify-center gap-1">
                            <Wind className="w-3 h-3 text-teal-400" /> Viento Máx.
                          </span>
                          <span className="text-sm font-bold text-amber-100 mt-1 block">
                            {weatherData.forecast.wind_speed_max} km/h
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* BLOQUE A: SECCIÓN DE LA COLECCIÓN PERSONAL */}
                  {weatherData.collection_recommendations && weatherData.collection_recommendations.length > 0 && (
                    <div className="pt-2 space-y-4">
                      <div>
                        <h3 className="text-lg font-serif text-neutral-100 flex items-center gap-2 font-medium">
                          <Sparkles className="w-4 h-4 text-emerald-400" />
                          De Tu Colección Personal
                        </h3>
                        <p className="text-xs text-neutral-400 mt-0.5">
                          Las mejores fragancias que ya posees optimizadas para el clima previsto.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {weatherData.collection_recommendations.map((item, idx) => (
                          <WeatherFragranceCard key={item.id || idx} item={item} isCollection={true} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* BLOQUE B: SECCIÓN DE DESCUBRIMIENTOS DEL CATÁLOGO */}
                  {weatherData.discovery_recommendations && weatherData.discovery_recommendations.length > 0 && (
                    <div className="pt-2 space-y-4">
                      <div>
                        <h3 className="text-lg font-serif text-neutral-100 flex items-center gap-2 font-medium">
                          <Compass className="w-4 h-4 text-amber-500" />
                          Alternativas Sugeridas para las Condiciones Meteorológicas
                        </h3>
                        <p className="text-xs text-neutral-400 mt-0.5">
                          Fragancias recomendadas del catálogo según la temperatura y humedad prevista.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {weatherData.discovery_recommendations.map((item, idx) => (
                          <WeatherFragranceCard key={item.id || idx} item={item} isCollection={false} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* FALLBACK: Si la respuesta backend antigua envía `clustering_alternatives` */}
                  {!weatherData.collection_recommendations && !weatherData.discovery_recommendations && weatherData.clustering_alternatives && weatherData.clustering_alternatives.length > 0 && (
                    <div className="pt-2 space-y-4">
                      <div>
                        <h3 className="text-lg font-serif text-neutral-100 flex items-center gap-2 font-medium">
                          <Sparkles className="w-4 h-4 text-amber-500" />
                          Alternativas Sugeridas para las Condiciones Meteorológicas
                        </h3>
                        <p className="text-xs text-neutral-400 mt-0.5">
                          Fragancias recomendadas de tu colección y del catálogo según el clima previsto.
                        </p>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {weatherData.clustering_alternatives.map((item, idx) => (
                          <WeatherFragranceCard key={item.id || idx} item={item} isCollection={item.in_user_collection} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB: MI COLECCIÓN */}
          {activeTab === 'collection' && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-serif text-neutral-100">Mi Colección Privada</h2>
                  <p className="text-xs text-neutral-400">Gestiona tus fragancias guardadas y filtra por sus propiedades olfativas.</p>
                </div>
              </div>

              <div className="bg-neutral-900/80 border border-neutral-800 p-4 rounded-2xl flex flex-wrap gap-4 items-center">
                <div className="flex items-center gap-2 text-xs uppercase text-amber-500 font-semibold tracking-wider">
                  <Filter className="w-4 h-4" />
                  <span>Filtros:</span>
                </div>

                <select 
                  value={filterStyle} 
                  onChange={(e) => setFilterStyle(e.target.value)}
                  className="bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 rounded-xl px-3 py-2 focus:border-amber-600 outline-none"
                >
                  <option value="">Todas las familias / estilo</option>
                  <option value="Oriental / gourmand">Oriental / gourmand</option>
                  <option value="Amaderado fresco e Informal">Amaderado fresco e Informal</option>
                  <option value="Limpio y atalcado">Limpio y atalcado</option>
                  <option value="Nicho / Retador">Nicho / Retador</option>
                  <option value="Dulce Nocturno / Versátil Elegante">Dulce Nocturno / Versátil Elegante</option>
                  <option value="Cuero Amaderado de Autoridad">Cuero Amaderado de Autoridad</option>
                </select>

                <select 
                  value={filterSeason} 
                  onChange={(e) => setFilterSeason(e.target.value)}
                  className="bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 rounded-xl px-3 py-2 focus:border-amber-600 outline-none"
                >
                  <option value="">Todas las estaciones</option>
                  <option value="Invierno">Invierno</option>
                  <option value="Verano">Verano</option>
                  <option value="Primavera">Primavera</option>
                  <option value="Otoño">Otoño</option>
                </select>

                <select 
                  value={filterTime} 
                  onChange={(e) => setFilterTime(e.target.value)}
                  className="bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 rounded-xl px-3 py-2 focus:border-amber-600 outline-none"
                >
                  <option value="">Cualquier momento</option> {/* IMPORTANTE: value="" */}
                  <option value="Día">Día</option>
                  <option value="Noche">Noche</option>
                </select>

                {(filterStyle || filterSeason || filterTime) && (
                  <button 
                    onClick={() => { setFilterStyle(''); setFilterSeason(''); setFilterTime(''); }}
                    className="text-xs text-neutral-400 hover:text-amber-400 underline ml-auto"
                  >
                    Limpiar Filtros
                  </button>
                )}
              </div>

              {isLoadingColl ? (
                <div className="text-center py-12 text-xs text-neutral-400">Cargando tu colección...</div>
              ) : userCollection.length === 0 ? (
                <div className="bg-neutral-900/40 border border-dashed border-neutral-800 rounded-2xl p-12 text-center space-y-4">
                  <div className="w-12 h-12 rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center mx-auto text-amber-500">
                    <Bookmark className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-serif text-neutral-200">Tu colección aún está vacía</h3>
                    <p className="text-xs text-neutral-400 max-w-md mx-auto mt-1 leading-relaxed">
                      Explora el catálogo o busca perfumes para añadirlos a tu reserva privada. Podrás clasificarlos y utilizarlos en tus recomendaciones personalizadas de IA.
                    </p>
                  </div>
                  <button 
                    onClick={() => setActiveTab('search')}
                    className="bg-amber-600 hover:bg-amber-500 text-neutral-950 text-xs px-5 py-2.5 rounded-xl font-semibold uppercase tracking-wider inline-flex items-center gap-2 transition"
                  >
                    <Search className="w-4 h-4" />
                    <span>Explorar Catálogo</span>
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
                    {userCollection.map((item) => (
                      <div key={item.id} className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-4 flex flex-col justify-between hover:border-neutral-700 transition">
                        <div className="flex gap-4">
                          <img src={item.bottle_image_url || 'https://images.unsplash.com/photo-1592945403244-b3fbafd7f539?auto=format&fit=crop&q=80&w=400'} alt={item.name} className="w-20 h-28 object-cover rounded-xl bg-neutral-950" />
                          <div className="flex-1">
                            <span className="text-[10px] uppercase tracking-wider text-amber-500 font-semibold">{item.designer}</span>
                            <h3 className="text-base font-serif text-neutral-100">{item.name}</h3>
                            <p className="text-[11px] text-neutral-400 mt-1 line-clamp-2">
                              <strong className="text-neutral-300">Notas:</strong> {item.top_notes?.concat(item.heart_notes || []).slice(0, 3).join(', ')}
                            </p>
                          </div>
                        </div>

                        <div className="mt-4 pt-3 border-t border-neutral-800/80 flex items-center justify-between">
                          <span className="text-[10px] text-neutral-500">Rating: ★ {item.global_rating || 'N/A'}</span>
                          <button 
                            onClick={() => handleToggleCollection(item.id)}
                            className="text-neutral-500 hover:text-red-400 p-1.5 transition flex items-center gap-1 text-xs"
                            title="Remover de colección"
                          >
                            <Trash2 className="w-4 h-4" />
                            <span>Remover</span>
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  {collTotalPages > 1 && (
                    <div className="flex items-center justify-between border-t border-neutral-800 pt-4 text-xs text-neutral-400">
                      <span>Mostrando página {collPage} de {collTotalPages} ({collTotalItems} perfumes en total)</span>
                      <div className="flex items-center gap-2">
                        <button 
                          disabled={collPage === 1}
                          onClick={() => { const p = collPage - 1; setCollPage(p); fetchUserCollection(p); }}
                          className="p-2 bg-neutral-900 border border-neutral-800 rounded-lg disabled:opacity-40 hover:bg-neutral-800"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="px-3 font-semibold text-amber-400">{collPage}</span>
                        <button 
                          disabled={collPage === collTotalPages}
                          onClick={() => { const p = collPage + 1; setCollPage(p); fetchUserCollection(p); }}
                          className="p-2 bg-neutral-900 border border-neutral-800 rounded-lg disabled:opacity-40 hover:bg-neutral-800"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB: BÚSQUEDA Y CATÁLOGO */}
          {activeTab === 'search' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-xl font-serif text-neutral-100">Explorar Catálogo</h2>
                <p className="text-xs text-neutral-400">Busca perfumes por nombre o marca y añádelos directamente a tu colección privada.</p>
              </div>

              <form onSubmit={handleSearchSubmit} className="flex gap-2">
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Busca por nombre (ej. Eros Versace, Santal 33)..."
                  className="flex-1 bg-neutral-900 border border-neutral-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-amber-600 transition text-neutral-100"
                />
                <button type="submit" disabled={isSearching} className="bg-amber-600 hover:bg-amber-500 text-neutral-950 px-6 rounded-xl text-sm font-semibold transition">
                  {isSearching ? 'Buscando...' : 'Buscar'}
                </button>
              </form>

              {notFoundQuery && (
                <div className="bg-amber-950/30 border border-amber-800/50 p-6 rounded-2xl space-y-4">
                  <div className="flex items-start gap-3">
                    <ShieldAlert className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-sm font-semibold text-amber-300">No encontramos "{notFoundQuery}" en el catálogo local</h3>
                      <p className="text-xs text-neutral-400 mt-1 leading-relaxed">
                        ¿Deseas realizar una búsqueda web avanzada para extraer este perfume en tiempo real?
                      </p>
                    </div>
                  </div>
                  <button onClick={handleTriggerScraper} disabled={isScraping} className="bg-amber-600 hover:bg-amber-500 text-neutral-950 text-xs px-5 py-2.5 rounded-xl font-semibold uppercase tracking-wider flex items-center gap-2 transition">
                    {isScraping ? <span>Extrayendo datos de la web...</span> : <><Sparkles className="w-4 h-4" /><span>Sí, extraer e importar perfume</span></>}
                  </button>
                </div>
              )}

              {searchResults.length > 0 && (
                <div className="space-y-6">
                  {isScrapedResult && (
                    <div className="bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs p-3 rounded-xl flex items-center gap-2">
                      <Check className="w-4 h-4" />
                      <span>Resultado obtenido mediante extracción web en tiempo real.</span>
                    </div>
                  )}

                  {searchResults.map((item) => {
                    const isSaved = userCollectionIds.includes(item.id);
                    return (
                      <div key={item.id} className="bg-neutral-900/60 border border-neutral-800 rounded-2xl p-6 grid md:grid-cols-3 gap-6">
                        <div className="flex flex-col items-center text-center">
                          <img src={item.bottle_image_url || 'https://images.unsplash.com/photo-1592945403244-b3fbafd7f539?auto=format&fit=crop&q=80&w=400'} alt={item.name} className="w-40 h-52 object-cover rounded-xl bg-neutral-950 mb-3" />
                          <h3 className="font-serif text-lg text-neutral-100">{item.name}</h3>
                          <p className="text-xs text-amber-500 uppercase tracking-wider">{item.designer}</p>
                          
                          <button 
                            onClick={() => handleToggleCollection(item.id)}
                            className={`mt-4 px-4 py-2 rounded-xl text-xs font-semibold tracking-wider uppercase flex items-center gap-2 transition ${
                              isSaved 
                                ? 'bg-emerald-950/60 border border-emerald-700 text-emerald-300 hover:bg-emerald-900/80' 
                                : 'bg-amber-600 hover:bg-amber-500 text-neutral-950'
                            }`}
                          >
                            {isSaved ? (
                              <>
                                <BookmarkCheck className="w-4 h-4" />
                                <span>En tu colección</span>
                              </>
                            ) : (
                              <>
                                <Plus className="w-4 h-4" />
                                <span>Agregar a mi colección</span>
                              </>
                            )}
                          </button>
                        </div>

                        <div className="md:col-span-2 space-y-4">
                          <h4 className="text-xs uppercase tracking-widest text-neutral-400 border-b border-neutral-800 pb-2">Pirámide Olfativa</h4>
                          <div className="space-y-2 text-xs">
                            <p><span className="text-amber-400 font-semibold">Salida:</span> {item.top_notes?.join(', ') || 'No especificada'}</p>
                            <p><span className="text-amber-500 font-semibold">Corazón:</span> {item.heart_notes?.join(', ') || 'No especificada'}</p>
                            <p><span className="text-amber-600 font-semibold">Fondo:</span> {item.base_notes?.join(', ') || 'No especificada'}</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB: PERFIL OLFATIVO IA */}
          {activeTab === 'profile' && (
            <div className="bg-neutral-900/60 border border-neutral-800 p-6 rounded-2xl space-y-8">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-neutral-800/80 pb-5">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1">
                      <Sparkles className="w-3 h-3" /> IA Profiling Engine
                    </span>
                  </div>
                  <h2 className="text-2xl font-serif text-neutral-100">Perfil Olfativo Vectorial</h2>
                  <p className="text-xs text-neutral-400">Análisis basado en la submuestra de tu colección privada y matriz de embeddings.</p>
                </div>
                <div className="flex items-center gap-3">
                  {profileData?.last_updated && (
                    <span className="text-[10px] text-neutral-500 bg-neutral-950 px-3 py-1.5 rounded-full border border-neutral-800">
                      Actualizado: {new Date(profileData.last_updated).toLocaleDateString()}
                    </span>
                  )}
                  <button
                    onClick={handleRecalculateProfile}
                    disabled={recalculatingProfile || loadingProfile}
                    className="bg-amber-500 hover:bg-amber-400 text-neutral-950 font-semibold px-4 py-2 rounded-xl text-xs transition disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-amber-500/10"
                    title="Forzar actualización del análisis olfativo"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${recalculatingProfile ? 'animate-spin' : ''}`} />
                    <span>{recalculatingProfile ? 'Analizando...' : 'Recalcular Perfil'}</span>
                  </button>
                </div>
              </div>

              {profileError && (
                <div className="p-4 bg-amber-950/20 border border-amber-800/40 text-amber-300 text-xs rounded-xl flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0 text-amber-500" />
                  <span>{profileError}</span>
                </div>
              )}

              {loadingProfile ? (
                <div className="py-20 text-center text-xs text-neutral-500 animate-pulse space-y-3">
                  <Sparkles className="w-8 h-8 mx-auto text-amber-500 animate-bounce" />
                  <p className="text-sm font-medium text-neutral-300">Extrayendo vectores y clustering de tu colección...</p>
                  <p className="text-neutral-500 text-[11px]">Procesando distancias en el espacio olfativo</p>
                </div>
              ) : profileData ? (
                <div className="space-y-8">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div className="lg:col-span-1 bg-gradient-to-br from-amber-950/30 via-neutral-950 to-neutral-950 border border-amber-900/30 p-5 rounded-xl relative overflow-hidden flex flex-col justify-between">
                      <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />
                      <div>
                        <span className="text-[10px] uppercase tracking-wider text-amber-500 font-semibold block mb-2 flex items-center gap-1.5">
                          <Compass className="w-3.5 h-3.5" /> Cluster Olfativo Predicho
                        </span>
                        <h3 className="text-lg font-serif text-amber-100 mb-2">
                          {profileData.cluster_info?.label || profileData.predicted_label || "Firma Olfativa Personal"}
                        </h3>
                        <p className="text-xs text-neutral-400 leading-relaxed">
                          {profileData.cluster_info?.description || "Tus selecciones reflejan una clara inclinación hacia combinaciones armónicas con fuerte presencia en piel."}
                        </p>
                      </div>
                      
                      {profileData.metrics?.total_owned && (
                        <div className="mt-4 pt-3 border-t border-neutral-800/60 flex items-center justify-between text-[11px] text-neutral-400">
                          <span>Fragancias analizadas:</span>
                          <span className="font-semibold text-amber-400">{profileData.metrics.total_owned} piezas</span>
                        </div>
                      )}
                    </div>

                    <div className="lg:col-span-2 bg-neutral-950/80 border border-neutral-800/80 p-5 rounded-xl relative flex flex-col justify-between">
                      <div>
                        <span className="text-[10px] uppercase tracking-wider text-amber-500 font-semibold block mb-2 flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5" /> Síntesis Olfativa Generada
                        </span>
                        <p className="text-sm text-neutral-200 italic font-serif leading-relaxed">
                          "{profileData.summary_text || profileData.summary}"
                        </p>
                      </div>

                      {profileData.metrics && (
                        <div className="mt-6 pt-4 border-t border-neutral-800/60 grid grid-cols-2 gap-4">
                          <div>
                            <div className="flex justify-between text-[11px] mb-1">
                              <span className="text-neutral-400">Duración Promedio</span>
                              <span className="text-amber-400 font-semibold">{Math.round((profileData.metrics.avg_longevity_score || 0.8) * 100)}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-amber-500 rounded-full transition-all duration-500" 
                                style={{ width: `${(profileData.metrics.avg_longevity_score || 0.8) * 100}%` }}
                              />
                            </div>
                          </div>

                          <div>
                            <div className="flex justify-between text-[11px] mb-1">
                              <span className="text-neutral-400">Proyección / Estela</span>
                              <span className="text-amber-400 font-semibold">{Math.round((profileData.metrics.avg_sillage_score || 0.75) * 100)}%</span>
                            </div>
                            <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-amber-500 rounded-full transition-all duration-500" 
                                style={{ width: `${(profileData.metrics.avg_sillage_score || 0.75) * 100}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-neutral-950/50 border border-neutral-800/60 p-5 rounded-xl space-y-3">
                      <h3 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Notas Dominantes
                        </span>
                        <span className="text-[10px] text-neutral-500">Top 5</span>
                      </h3>
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {profileData.dominant_notes?.length > 0 ? (
                          profileData.dominant_notes.map((note, idx) => (
                            <span key={idx} className="bg-amber-500/10 text-amber-300 border border-amber-500/20 text-xs px-3 py-1.5 rounded-lg flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                              {note}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-neutral-600 italic">Sin notas registradas</span>
                        )}
                      </div>
                    </div>

                    <div className="bg-neutral-950/50 border border-neutral-800/60 p-5 rounded-xl space-y-3">
                      <h3 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Filter className="w-3.5 h-3.5 text-amber-500" /> Acordes Predominantes
                        </span>
                        <span className="text-[10px] text-neutral-500">Frecuencia</span>
                      </h3>
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {profileData.preferred_accords?.length > 0 ? (
                          profileData.preferred_accords.map((accord, idx) => (
                            <span key={idx} className="bg-neutral-800 text-neutral-200 text-xs px-3 py-1.5 rounded-lg border border-neutral-700/50">
                              {accord}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-neutral-600 italic">Sin acordes registrados</span>
                        )}
                      </div>
                    </div>

                    <div className="bg-neutral-950/50 border border-neutral-800/60 p-5 rounded-xl space-y-3">
                      <h3 className="text-xs font-semibold text-neutral-300 uppercase tracking-wider flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-amber-500" /> Climas y Estaciones
                        </span>
                        <span className="text-[10px] text-neutral-500">Afinidad</span>
                      </h3>
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {profileData.preferred_seasons?.length > 0 ? (
                          profileData.preferred_seasons.map((season, idx) => (
                            <span key={idx} className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs px-3 py-1.5 rounded-lg capitalize">
                              {season}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-neutral-600 italic">Sin estaciones registradas</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {profileData.recommendations?.length > 0 && (
                    <div className="pt-6 border-t border-neutral-800/80 space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-base font-serif text-neutral-100 flex items-center gap-2">
                            <TrendingUp className="w-4 h-4 text-amber-500" />
                            Recomendaciones Sugeridas por Tu Perfil
                          </h3>
                          <p className="text-xs text-neutral-400">Fragancias fuera de tu colección con mayor similitud vectorial.</p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
                        {profileData.recommendations.map((rec) => (
                          <div 
                            key={rec.id} 
                            className="bg-neutral-950 border border-neutral-800 hover:border-amber-900/50 p-4 rounded-xl transition duration-200 flex flex-col justify-between group"
                          >
                            <div className="space-y-3">
                              <div className="w-full h-36 bg-neutral-900 rounded-lg overflow-hidden flex items-center justify-center p-2 relative">
                                {rec.bottle_image_url ? (
                                  <img 
                                    src={rec.bottle_image_url} 
                                    alt={rec.name} 
                                    className="h-full object-contain group-hover:scale-105 transition duration-300" 
                                  />
                                ) : (
                                  <Droplets className="w-8 h-8 text-neutral-700" />
                                )}

                                {rec.similarity_score && (
                                  <span className="absolute top-2 right-2 bg-amber-500 text-neutral-950 font-bold text-[10px] px-2 py-0.5 rounded-full shadow">
                                    {Math.round(rec.similarity_score * 100)}% Match
                                  </span>
                                )}
                              </div>

                              <div>
                                <p className="text-[11px] text-amber-500 font-medium uppercase tracking-wider">{rec.designer}</p>
                                <h4 className="text-sm font-semibold text-neutral-100 truncate">{rec.name}</h4>
                                {rec.olfactory_profile_label && (
                                  <p className="text-[11px] text-neutral-400 mt-1 line-clamp-1">{rec.olfactory_profile_label}</p>
                                )}
                              </div>
                            </div>

                            <div className="mt-4 pt-3 border-t border-neutral-900 flex items-center justify-between text-xs text-neutral-400">
                              <span className="flex items-center gap-1 text-amber-400 font-medium">
                                ★ {rec.global_rating ? Number(rec.global_rating).toFixed(1) : 'N/A'}
                              </span>
                              <button className="text-[11px] text-neutral-300 hover:text-amber-400 transition flex items-center gap-1">
                                Ver detalle <ArrowRight className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                </div>
              ) : (
                <div className="bg-neutral-950/40 border border-dashed border-neutral-800 rounded-xl p-12 text-center space-y-4">
                  <Compass className="w-10 h-10 text-neutral-600 mx-auto" />
                  <div className="space-y-1">
                    <h3 className="text-sm font-semibold text-neutral-300">Perfil Olfativo No Disponible</h3>
                    <p className="text-xs text-neutral-400 max-w-sm mx-auto leading-relaxed">
                      Aún no cuentas con fragancias marcadas como <span className="text-amber-400 font-medium">"owned"</span> en tu colección privada para proyectar tu vector de preferencias.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB: ASISTENTE IA */}
          {activeTab === 'assistant' && (
            <div className="bg-neutral-900/60 border border-neutral-800 rounded-2xl flex flex-col h-[650px] overflow-hidden shadow-2xl relative">
              
              {/* HEADER DEL CHAT */}
              <div className="p-4 border-b border-neutral-800/80 bg-neutral-950/80 backdrop-blur-md flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-600 to-amber-400 flex items-center justify-center text-neutral-950 shadow-md">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-serif font-semibold text-neutral-100 flex items-center gap-2">
                      Aura — Sommelier Olfativa
                      <span className="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-sans font-normal">
                        gpt-4o-mini
                      </span>
                    </h3>
                    <p className="text-[11px] text-neutral-400">Asesoría experta en notas, ocasión, personalidad y dupes</p>
                  </div>
                </div>

                <button 
                  onClick={() => setChatMessages([
                    { role: 'assistant', content: 'Hola, soy Aura, tu Sommelier Olfativa Senior. ¿En qué puedo ayudarte hoy a explorar tu colección o encontrar tu próxima fragancia firma?' }
                  ])}
                  className="text-[11px] text-neutral-400 hover:text-amber-400 p-2 rounded-lg hover:bg-neutral-900 transition flex items-center gap-1.5"
                  title="Reiniciar conversación"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Nueva Consulta</span>
                </button>
              </div>

              {/* HISTORIAL DE CHAT */}
              <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-neutral-950/40">
                {chatMessages.map((msg, idx) => {
                  const isUser = msg.role === 'user';
                  return (
                    <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 text-xs leading-relaxed space-y-2 ${
                        isUser 
                          ? 'bg-amber-600 text-neutral-950 font-medium rounded-tr-none shadow-md' 
                          : 'bg-neutral-900/90 text-neutral-200 border border-neutral-800 rounded-tl-none shadow-md'
                      }`}>
                        {msg.content.split('\n\n').map((paragraph, pIdx) => (
                          <p key={pIdx} className="whitespace-pre-wrap">
                            {paragraph}
                          </p>
                        ))}
                      </div>
                    </div>
                  );
                })}

                {isAiReplying && (
                  <div className="flex justify-start">
                    <div className="bg-neutral-900/90 text-neutral-400 border border-neutral-800 rounded-2xl rounded-tl-none p-4 text-xs flex items-center gap-3">
                      <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                      <span>{audioProcessing ? 'Transcribiendo audio con Whisper...' : 'Aura está analizando las familias olfativas...'}</span>
                    </div>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>

              {/* ALERTA DE ERROR */}
              {chatError && (
                <div className="px-4 py-2 bg-red-950/60 border-t border-red-800/50 text-red-300 text-xs flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                    <span>{chatError}</span>
                  </div>
                  <button onClick={() => setChatError('')} className="text-red-400 underline text-[10px]">Cerrar</button>
                </div>
              )}

              {/* INPUT DE CHAT Y BOTÓN DE MICRÓFONO */}
              <div className="p-4 border-t border-neutral-800/80 bg-neutral-950">
                <form onSubmit={handleSendTextMessage} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={currentMessage}
                    onChange={(e) => setCurrentMessage(e.target.value)}
                    placeholder={isRecording ? "Grabando audio desde el micrófono..." : "Escribe tu duda o pide una recomendación olfativa..."}
                    disabled={isRecording || isAiReplying}
                    className="flex-1 bg-neutral-900 border border-neutral-800 text-neutral-100 rounded-xl px-4 py-3 text-xs focus:outline-none focus:border-amber-600 transition disabled:opacity-50 placeholder:text-neutral-500"
                  />

                  <button
                    type="button"
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={isAiReplying}
                    className={`p-3 rounded-xl transition flex items-center justify-center shrink-0 ${
                      isRecording 
                        ? 'bg-red-600 text-white animate-pulse' 
                        : 'bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-amber-400 hover:border-amber-600/50'
                    }`}
                    title={isRecording ? "Detener grabación y enviar audio" : "Grabar mensaje de voz"}
                  >
                    {isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>

                  <button
                    type="submit"
                    disabled={!currentMessage.trim() || isAiReplying || isRecording}
                    className="bg-amber-600 hover:bg-amber-500 text-neutral-950 p-3 rounded-xl transition disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                    title="Enviar mensaje"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>

                {isRecording && (
                  <p className="text-[10px] text-amber-500 mt-2 text-center animate-pulse flex items-center justify-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-500"></span>
                    Escuchando... Presiona el botón del micrófono nuevamente para enviar.
                  </p>
                )}
              </div>

            </div>
          )}
        </main>
      </div>
    </div>
  );
}

{/* COMPONENTE REUTILIZABLE PARA TARJETAS DE RECOMENDACIÓN POR CLIMA */}
function WeatherFragranceCard({ item, isCollection }) {
  return (
    <div className="bg-neutral-950 border border-neutral-800/90 rounded-xl p-4 flex flex-col justify-between space-y-4 relative hover:border-neutral-700 transition duration-200">
      <div className="space-y-3">
        {/* Encabezado: Familia y Badge de Origen */}
        <div className="flex items-start justify-between gap-2">
          <span className="text-[11px] font-bold text-amber-500 uppercase tracking-wider leading-tight">
            {item.family || item.cluster || 'FAMILIA RECOMENDADA'}
          </span>

          {isCollection ? (
            <span className="bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 text-[9px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap">
              Tu Colección
            </span>
          ) : (
            <span className="bg-neutral-900 text-neutral-400 border border-neutral-800 text-[9px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap">
              Descubrimiento
            </span>
          )}
        </div>

        {/* Imagen + Marca y Nombre */}
        <div className="flex items-center gap-3">
          {item.bottle_image_url ? (
            <div className="w-16 h-20 bg-neutral-900/80 border border-neutral-800 rounded-lg p-1 flex-shrink-0 flex items-center justify-center overflow-hidden">
              <img
                src={item.bottle_image_url}
                alt={item.name || 'Perfume'}
                className="w-full h-full object-contain"
                loading="lazy"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
            </div>
          ) : (
            <div className="w-16 h-20 bg-neutral-900/50 border border-neutral-800 rounded-lg flex-shrink-0 flex items-center justify-center text-neutral-600 text-[10px]">
              Sin Foto
            </div>
          )}

          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-serif font-bold text-neutral-100 truncate leading-snug">
              {item.name || item.label || 'Perfume Sugerido'}
            </h4>
            <p className="text-xs text-neutral-400 truncate mt-0.5 font-medium">
              {item.designer || 'Casa Diseñadora'}
            </p>
          </div>
        </div>

        {/* Descripción o notas si existen */}
        {item.description && (
          <p className="text-xs text-neutral-400 leading-relaxed line-clamp-2">
            {item.description}
          </p>
        )}
      </div>

      {/* Footer: Afinidad climática */}
      <div className="pt-2 border-t border-neutral-900 flex justify-between items-center text-xs text-neutral-400">
        <span className="text-[11px] text-neutral-400">Afinidad climática</span>
        <span className="text-neutral-200 font-mono font-semibold">
          {item.similarity_score !== undefined && item.similarity_score !== null
            ? `${Math.round(item.similarity_score * 100)}%`
            : '100%'}
        </span>
      </div>
    </div>
  );
}