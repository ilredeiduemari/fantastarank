import streamlit as st
import pandas as pd

# ==========================================
# CONFIGURAZIONE LEGA
# ==========================================
REGOLE_ROSA = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
BUDGET_INIZIALE = 500
MIA_SQUADRA = "la_mia_squadra"
NOMI_PARTECIPANTI = [
    "la_mia_squadra", "avversario_1", "avversario_2", 
    "avversario_3", "avversario_4", "avversario_5", 
    "avversario_6", "avversario_7"
]

# ==========================================
# CLASSI E MOTORE LOGICO
# ==========================================
class Giocatore:
    def __init__(self, nome, ruolo, valore_base, rendimento_atteso):
        self.nome = str(nome).strip()
        self.ruolo = str(ruolo).strip()
        self.valore_base = max(1, float(valore_base)) 
        self.rendimento_atteso = float(rendimento_atteso)
        self.squadra = None
        self.prezzo_acquisto = 0

class Squadra:
    def __init__(self, nome, budget, regole_rosa):
        self.nome = nome
        self.budget_iniziale = budget
        self.budget_residuo = budget
        self.rosa = []
        self.necessita_ruoli = regole_rosa.copy() 

    def acquista(self, giocatore, prezzo):
        self.rosa.append(giocatore)
        self.budget_residuo -= prezzo
        self.necessita_ruoli[giocatore.ruolo] -= 1
        giocatore.squadra = self.nome
        giocatore.prezzo_acquisto = prezzo

class GestoreAsta:
    def __init__(self, lista_giocatori, lista_squadre, mia_squadra):
        self.giocatori = {g.nome.lower(): g for g in lista_giocatori}
        self.squadre = {s.nome.lower(): s for s in lista_squadre}
        self.mia_squadra = mia_squadra.lower()
        self.budget_totale_iniziale = sum(s.budget_iniziale for s in lista_squadre)
        self.ordine_ruoli = ['P', 'D', 'C', 'A']

    def get_svincolati(self):
        return [g.nome for g in self.giocatori.values() if g.squadra is None]

    def _get_ruolo_attivo(self):
        for ruolo in self.ordine_ruoli:
            if sum(s.necessita_ruoli[ruolo] for s in self.squadre.values()) > 0:
                return ruolo
        return None 

    def aggiudica_giocatore(self, nome_giocatore, nome_squadra, prezzo):
        giocatore = self.giocatori[nome_giocatore.lower()]
        squadra = self.squadre[nome_squadra.lower()]
        squadra.acquista(giocatore, prezzo)
        
    def _calcola_inflazione_lega(self):
        return sum(s.budget_residuo for s in self.squadre.values()) / self.budget_totale_iniziale

    def _calcola_scarsita_ruolo(self, ruolo):
        liberi = [g for g in self.giocatori.values() if g.squadra is None and g.ruolo == ruolo]
        necessita_totale = sum(s.necessita_ruoli[ruolo] for s in self.squadre.values() if s.necessita_ruoli[ruolo] > 0)
        if len(liberi) == 0: return 2.0
        return max(0.8, min(2.0, necessita_totale / len(liberi)))

    def calcola_fantavalore_dinamico(self, nome_giocatore):
        giocatore = self.giocatori[nome_giocatore.lower()]
        if giocatore.squadra is not None: return 0
        inflazione = self._calcola_inflazione_lega()
        scarsita = self._calcola_scarsita_ruolo(giocatore.ruolo)
        fabbisogno_mio = self.squadre[self.mia_squadra].necessita_ruoli[giocatore.ruolo]
        molt_fabbisogno = 1.0 + (fabbisogno_mio * 0.05) if fabbisogno_mio > 0 else 0.1
        return max(1, round(giocatore.valore_base * inflazione * scarsita * molt_fabbisogno))

    def suggerisci_prossima_chiamata(self):
        ruolo_attivo = self._get_ruolo_attivo()
        if not ruolo_attivo: return None, "Asta Completata"
            
        svincolati = [g for g in self.giocatori.values() if g.squadra is None and g.ruolo == ruolo_attivo]
        ranking = []
        K_PENALITA = 15 
        
        for g in svincolati:
            val = self.calcola_fantavalore_dinamico(g.nome)
            if val > 0:
                ind = (g.rendimento_atteso ** 2) / (val + K_PENALITA)
                ranking.append({
                    'Nome': g.nome, 
                    'FantaValue': g.rendimento_atteso, 
                    'Prezzo Giusto': val,
                    'Indice Strategico': round(ind, 2)
                })
        
        df = pd.DataFrame(ranking)
        if not df.empty:
            df = df.sort_values(by=['Indice Strategico'], ascending=False).head(10)
            # Resetta l'indice per nascondere i numeri di riga inestetici
            df = df.reset_index(drop=True)
            return df, ruolo_attivo
        return None, ruolo_attivo

    def analizza_strategia_asta(self, nome_giocatore):
        giocatore = self.giocatori[nome_giocatore.lower()]
        valore_max = self.calcola_fantavalore_dinamico(nome_giocatore)
        pericolosi, lasciare = [], []
        
        for nome_squadra, squadra in self.squadre.items():
            if nome_squadra == self.mia_squadra: continue
            necessita = squadra.necessita_ruoli[giocatore.ruolo]
            budget = squadra.budget_residuo
            
            if necessita > 0 and budget >= valore_max:
                pericolosi.append(f"{squadra.nome.upper()} ({budget}cr)")
            elif necessita <= 0 or budget < (valore_max * 0.5):
                lasciare.append(squadra.nome.upper())
                
        return valore_max, pericolosi, lasciare

# ==========================================
# INIZIALIZZAZIONE SESSIONE
# ==========================================
st.set_page_config(page_title="FantaAsta 2024", page_icon="🏆", layout="centered")

@st.cache_data
def carica_dati():
    df = pd.read_csv('giocatori.csv')
    return [Giocatore(row['Nome'], row['Ruolo'], row['Media acquisto'], row['FantaValue']) for _, row in df.iterrows()]

if 'asta' not in st.session_state:
    try:
        lista_giocatori = carica_dati()
        squadre = [Squadra(n, BUDGET_INIZIALE, REGOLE_ROSA) for n in NOMI_PARTECIPANTI]
        st.session_state.asta = GestoreAsta(lista_giocatori, squadre, MIA_SQUADRA)
    except Exception as e:
        st.error(f"Errore caricamento CSV: {e}")
        st.stop()

asta = st.session_state.asta

# ==========================================
# INTERFACCIA UTENTE (UI)
# ==========================================
st.title("🏆 Gestionale Asta Live")

tab1, tab2, tab3, tab4 = st.tabs(["🛒 Aggiudica", "💡 Suggerimenti", "🔍 Analisi", "📊 Situazione"])

# --- TAB 1: AGGIUDICA ---
with tab1:
    st.header("Nuovo Acquisto")
    col1, col2 = st.columns(2)
    
    # Crea un menu a tendina intelligente solo con i giocatori ancora liberi
    giocatori_liberi = sorted(asta.get_svincolati())
    
    with col1:
        giocatore_scelto = st.selectbox("Giocatore", giocatori_liberi)
    with col2:
        squadra_scelta = st.selectbox("Squadra Acquirente", [s.upper() for s in NOMI_PARTECIPANTI])
        
    prezzo_scelto = st.number_input("Prezzo di Acquisto", min_value=1, max_value=BUDGET_INIZIALE, value=1, step=1)
    
    if st.button("Conferma Acquisto", type="primary", use_container_width=True):
        asta.aggiudica_giocatore(giocatore_scelto, squadra_scelta, prezzo_scelto)
        st.success(f"✅ {giocatore_scelto.upper()} andato a {squadra_scelta} per {prezzo_scelto} crediti!")

# --- TAB 2: SUGGERIMENTI STRATEGICI ---
with tab2:
    st.header("Migliori Chiamate")
    df_sugg, ruolo = asta.suggerisci_prossima_chiamata()
    
    if df_sugg is not None:
        st.subheader(f"Fase Attuale: Ruolo {ruolo}")
        st.info("I giocatori con Indice Strategico più alto sono gli affari migliori ORA.")
        st.dataframe(df_sugg, use_container_width=True)
    else:
        st.success(ruolo) # Stampa "Asta Completata"

# --- TAB 3: ANALISI GIOCATORE ---
with tab3:
    st.header("Radar Avversari")
    gio_analizza = st.selectbox("Scegli un giocatore da analizzare", giocatori_liberi, key="analizza")
    
    if st.button("Analizza", use_container_width=True):
        valore_max, pericolosi, lasciare = asta.analizza_strategia_asta(gio_analizza)
        
        st.metric("Soglia Massima Consigliata", f"{valore_max} cr")
        
        st.error(f"**Da CONTRASTARE (Pericolosi):**\n" + (", ".join(pericolosi) if pericolosi else "Nessuno"))
        st.success(f"**Puoi lasciarli rilanciare:**\n" + (", ".join(lasciare) if lasciare else "Nessuno"))

# --- TAB 4: SITUAZIONE LEGA ---
with tab4:
    st.header("Budget e Rose")
    dati_lega = []
    for s_nome, s_obj in asta.squadre.items():
        comprati = sum(REGOLE_ROSA.values()) - sum(s_obj.necessita_ruoli.values())
        dati_lega.append({
            'Squadra': s_obj.nome.upper(),
            'Budget Rimasto': s_obj.budget_residuo,
            'Giocatori Presi': comprati
        })
    df_lega = pd.DataFrame(dati_lega).sort_values(by='Budget Rimasto', ascending=False).reset_index(drop=True)
    st.dataframe(df_lega, use_container_width=True)