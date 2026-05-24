from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
app_fast = FastAPI()

app_fast.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from postgrest import SyncPostgrestClient
import os
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: Variables are empty!")
else:
    print("Success: Variables loaded!")

print(f"DEBUG: URL is {SUPABASE_URL}")

# ─── Connexion Supabase ───────────────────────────────────────────
try:
    supabase = SyncPostgrestClient(
        f"{SUPABASE_URL}/rest/v1",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"   # ← FIX: retourne les données insérées
        }
    )
    SUPABASE_OK = True
    print("[SUPABASE] Connexion OK")
except Exception as _e:
    print(f"WARNING: Supabase connection failed: {_e}")
    supabase = None
    SUPABASE_OK = False


# ─── Synchronisation Supabase helper CORRIGÉE ────────────────────
def sync_to_supabase(table: str, action: str, data: dict = None, match: dict = None):
    """
    Synchronise une opération vers Supabase.
    FIX: Ne jamais envoyer les colonnes PRIMARY KEY auto-générées (SERIAL).
    action: 'insert', 'update', 'delete'
    """
    global supabase, SUPABASE_OK
    if not SUPABASE_OK or supabase is None:
        print(f"[SUPABASE SKIP] Connexion non disponible pour {table}/{action}")
        return

    # ─── Colonnes PK auto-générées à exclure des INSERT ───────────
    # Supabase (PostgreSQL SERIAL) génère ces IDs automatiquement.
    # Les envoyer cause un conflit ou est simplement ignoré.
    PK_EXCLUSIONS = {
        'Utilisateur': 'ID_utilisateur',
        'Chauffeur':   'Code_chauffeur',
        'Client':      'Code_client',
        'Administrateur': 'Code_administrateur',
        'Bus':         'Code_bus',
        'Ligne':       'Code_Ligne',
        'Parcours':    'ID_parcours',
        'Historique':  'ID_historique',
        'Incident':    'ID_incident',
        'Avis':        'ID_avis',
        'ResetCode':   'ID',
    }

    try:
        if action == 'insert' and data:
            # ← FIX PRINCIPAL: on retire la clé primaire pour laisser Supabase la générer
            clean_data = dict(data)
            pk_col = PK_EXCLUSIONS.get(table)
            if pk_col and pk_col in clean_data:
                del clean_data[pk_col]

            result = supabase.from_(table).insert(clean_data).execute()
            print(f"[SUPABASE OK] INSERT {table}: {result.data}")

        elif action == 'update' and data and match:
            q = supabase.from_(table).update(data)
            for col, val in match.items():
                q = q.eq(col, val)
            result = q.execute()
            print(f"[SUPABASE OK] UPDATE {table}: {result.data}")

        elif action == 'delete' and match:
            q = supabase.from_(table).delete()
            for col, val in match.items():
                q = q.eq(col, val)
            result = q.execute()
            print(f"[SUPABASE OK] DELETE {table}: {result.data}")

    except Exception as _se:
        print(f"[SUPABASE ERROR] table={table} action={action} data={data} match={match} err={_se}")


# ─── Flask App ────────────────────────────────────────────────────
from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import re
from flask_bcrypt import Bcrypt
from datetime import datetime
import random
import string
from flask_mail import Mail, Message

# ─── NLP & Gemini AI Libraries ───────────────────────────────────
try:
    from textblob import TextBlob
    from deep_translator import GoogleTranslator
    HAS_NLP = True
except ImportError:
    HAS_NLP = False

try:
    from langdetect import detect as langdetect_detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

try:
    import google.generativeai as genai
    import json
    GEMINI_API_KEY = "AIzaSyAs1JV2C1hVXZbQAyrCPi3PMY2NNIAWylA"
    genai.configure(api_key=GEMINI_API_KEY)
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

# ─── Flask-Mail ───────────────────────────────────────────────────
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'khawlabenhmid2@gmail.com'
app.config['MAIL_PASSWORD'] = 'sztw sklu nyav ypzz'
app.config['MAIL_DEFAULT_SENDER'] = 'khawlabenhmid2@gmail.com'
mail = Mail(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_trans.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Init Tables ──────────────────────────────────────────────────
def init_all_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

    try:
        cursor.execute("ALTER TABLE Incident ADD COLUMN Performance_IA FLOAT")
    except: pass
    try:
        cursor.execute("ALTER TABLE Incident ADD COLUMN Statut TEXT DEFAULT 'Signalé'")
    except: pass
    try:
        cursor.execute("ALTER TABLE Incident ADD COLUMN Code_bus INTEGER")
    except: pass

    try:
        cursor.execute("""
            UPDATE Incident 
            SET Code_bus = (SELECT Code_bus FROM Ligne WHERE Ligne.Code_Ligne = Incident.Code_Ligne)
            WHERE Code_bus IS NULL OR Code_bus NOT IN (SELECT Code_bus FROM Bus)
        """)
        cursor.execute("""
            UPDATE Incident 
            SET Code_bus = (SELECT Code_bus FROM Bus WHERE Bus.Code_chauffeur = Incident.Code_chauffeur LIMIT 1)
            WHERE Code_bus IS NULL OR Code_bus NOT IN (SELECT Code_bus FROM Bus)
        """)
        cursor.execute("DELETE FROM Incident WHERE Code_bus IS NOT NULL AND Code_bus NOT IN (SELECT Code_bus FROM Bus)")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS Utilisateur (
        ID_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
        Nom TEXT, Email TEXT UNIQUE, Mot_de_passe TEXT, Role TEXT, Photo TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Chauffeur (
        Code_chauffeur INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER, Performance_score FLOAT DEFAULT 5.0,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Client (
        Code_client INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Administrateur (
        Code_administrateur INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Bus (
        Code_bus INTEGER PRIMARY KEY AUTOINCREMENT,
        Numero_bus TEXT UNIQUE, Etat TEXT, Code_chauffeur INTEGER,
        FOREIGN KEY (Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur) ON DELETE SET NULL)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Ligne (
        Code_Ligne INTEGER PRIMARY KEY AUTOINCREMENT,
        Libelle TEXT, Description TEXT, Code_bus INTEGER,
        FOREIGN KEY(Code_bus) REFERENCES Bus(Code_bus))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Parcours (
        ID_parcours INTEGER PRIMARY KEY AUTOINCREMENT,
        Depart TEXT, Arrivee TEXT, Heure_depart TEXT, Heure_arrivee TEXT, Code_Ligne INTEGER,
        FOREIGN KEY(Code_Ligne) REFERENCES Ligne(Code_Ligne))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Historique (
        ID_historique INTEGER PRIMARY KEY AUTOINCREMENT,
        Date TEXT, Heure_fin TEXT, Statut TEXT, Depart TEXT, Arrivee TEXT,
        Performance_IA FLOAT, ID_parcours INTEGER, Code_chauffeur INTEGER,
        FOREIGN KEY(ID_parcours) REFERENCES Parcours(ID_parcours),
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Incident (
        ID_incident INTEGER PRIMARY KEY AUTOINCREMENT,
        Description TEXT, Date TEXT, Code_chauffeur INTEGER, Code_Ligne INTEGER,
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur),
        FOREIGN KEY(Code_Ligne) REFERENCES Ligne(Code_Ligne))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Avis (
        ID_avis INTEGER PRIMARY KEY AUTOINCREMENT,
        Code_client INTEGER, ID_historique INTEGER, Note INTEGER,
        Commentaire TEXT, Date TEXT, Sentiment_score FLOAT,
        Sentiment_label TEXT, Keywords TEXT, Category TEXT, ID_parcours INTEGER,
        FOREIGN KEY(Code_client) REFERENCES Client(Code_client),
        FOREIGN KEY(ID_historique) REFERENCES Historique(ID_historique),
        FOREIGN KEY(ID_parcours) REFERENCES Parcours(ID_parcours))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ResetCode (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Email TEXT, Code TEXT, Expiration DATETIME)''')

    hashed_pw = bcrypt.generate_password_hash('123456').decode('utf-8')
    cursor.execute('''INSERT OR IGNORE INTO Utilisateur (Nom, Email, Mot_de_passe, Role) 
                      VALUES (?, ?, ?, ?)''', ('Khawla', 'khawla@email.com', hashed_pw, 'admin'))

    conn.commit()
    conn.close()
    print("OK: Les tables sont creees avec succes !")


# ─── AUTH ─────────────────────────────────────────────────────────
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    nom = data.get('nom')
    email = data.get('email').lower().strip()
    password = data.get('password')
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        check = cursor.execute("SELECT * FROM Utilisateur WHERE Email = ?", (email,)).fetchone()
        if check:
            conn.close()
            return jsonify({"message": "Email déjà utilisé"}), 400

        cursor.execute(
            "INSERT INTO Utilisateur (Nom, Email, Mot_de_passe, Role) VALUES (?, ?, ?, ?)",
            (nom, email, hashed_pw, 'client')
        )
        new_id = cursor.lastrowid
        cursor.execute("INSERT INTO Client (ID_utilisateur) VALUES (?)", (new_id,))
        new_client_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # ← FIX: pas de clé primaire dans l'insert Supabase
        sync_to_supabase('Utilisateur', 'insert', {
            'Nom': nom, 'Email': email, 'Mot_de_passe': hashed_pw, 'Role': 'client'
        })
        sync_to_supabase('Client', 'insert', {'ID_utilisateur': new_id})
        return jsonify({"message": "Compte créé"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return jsonify({"error": "Missing email or password"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Utilisateur WHERE Email = ?", (email,))
        user = cursor.fetchone()

        if user:
            if bcrypt.check_password_hash(user['Mot_de_passe'], password):
                conn.close()
                return jsonify({
                    "message": "Login successful",
                    "id":    user['ID_utilisateur'],
                    "nom":   user['Nom'],
                    "email": user['Email'],
                    "role":  user['Role'],
                    "photo": user['Photo'] or ""
                }), 200
            else:
                conn.close()
                return jsonify({"error": "Invalid password"}), 401
        else:
            conn.close()
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        print("ERROR IN LOGIN:", str(e))
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


# ─── FORGOT PASSWORD ──────────────────────────────────────────────
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    if not email:
        return jsonify({"error": "Email est obligatoire"}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM Utilisateur WHERE Email = ?', (email,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Aucun compte trouvé avec cet email"}), 404

    code = ''.join(random.choices(string.digits, k=6))
    conn.execute('DELETE FROM ResetCode WHERE Email = ?', (email,))
    conn.execute('INSERT INTO ResetCode (Email, Code) VALUES (?, ?)', (email, code))
    conn.commit()
    conn.close()

    try:
        msg = Message("Code de vérification SMART-TRANS", recipients=[email])
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 15px;">
            <h1 style="color: #008080; text-align:center;">SMART-TRANS</h1>
            <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; text-align: center;">
                <p>Bonjour <strong>{user['Nom']}</strong>,</p>
                <p>Votre code de vérification :</p>
                <div style="background: #008080; color: white; font-size: 32px; font-weight: bold; padding: 15px; border-radius: 8px; display: inline-block; letter-spacing: 5px; margin: 20px 0;">
                    {code}
                </div>
                <p style="font-size: 12px; color: #888;">Valable 15 minutes. Ne le partagez avec personne.</p>
            </div>
            <p style="text-align:center; color: #008080; font-weight: bold;">L'équipe SMART-TRANS</p>
        </div>
        """
        mail.send(msg)
        return jsonify({"message": "Code envoyé par email"}), 200
    except Exception as e:
        print(f"Error envoi email: {e}")
        return jsonify({"error": "Erreur lors de l'envoi de l'email."}), 500


@app.route('/verify-reset-code', methods=['POST'])
def verify_reset_code():
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    code = data.get('code', '')
    conn = get_db_connection()
    res = conn.execute('SELECT * FROM ResetCode WHERE Email = ? AND Code = ?', (email, code)).fetchone()
    conn.close()
    if res:
        return jsonify({"message": "Code valide"}), 200
    return jsonify({"error": "Code invalide ou expiré"}), 400


@app.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    code = data.get('code', '')
    new_password = data.get('new_password', '')

    if len(new_password) < 6:
        return jsonify({"error": "Le mot de passe doit contenir au moins 6 caractères"}), 400

    conn = get_db_connection()
    res = conn.execute('SELECT * FROM ResetCode WHERE Email = ? AND Code = ?', (email, code)).fetchone()
    if not res:
        conn.close()
        return jsonify({"error": "Action non autorisée"}), 403

    hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
    conn.execute('UPDATE Utilisateur SET Mot_de_passe = ? WHERE Email = ?', (hashed_pw, email))
    conn.execute('DELETE FROM ResetCode WHERE Email = ?', (email,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Mot de passe réinitialisé avec succès"}), 200


# ─── BUS ──────────────────────────────────────────────────────────
@app.route('/get_buses', methods=['GET'])
def get_buses():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Bus ORDER BY Code_bus DESC")
        buses = [dict(ix) for ix in cursor.fetchall()]
        conn.close()
        return jsonify(buses)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_bus', methods=['POST'])
def add_bus():
    try:
        data = request.get_json()
        numero = data.get('Numero_bus')
        etat = data.get('Etat')
        id_chauffeur = data.get('Code_chauffeur')

        conn = get_db_connection()
        cur = conn.execute(
            'INSERT INTO Bus (Numero_bus, Etat, Code_chauffeur) VALUES (?, ?, ?)',
            (numero, etat, id_chauffeur)
        )
        conn.commit()
        conn.close()

        # ← FIX: pas de Code_bus (PK) dans l'insert
        sync_to_supabase('Bus', 'insert', {
            'Numero_bus': numero, 'Etat': etat, 'Code_chauffeur': id_chauffeur
        })
        return jsonify({"status": "success", "message": "Bus ajouté"}), 201
    except Exception as e:
        print(f"Erreur add_bus: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/update_bus/<int:id>', methods=['PUT'])
def update_bus(id):
    try:
        data = request.get_json()
        numero = data.get('Numero_bus')
        etat = data.get('Etat')
        id_chauffeur = data.get('Code_chauffeur')

        conn = get_db_connection()
        conn.execute(
            'UPDATE Bus SET Numero_bus = ?, Etat = ?, Code_chauffeur = ? WHERE Code_bus = ?',
            (numero, etat, id_chauffeur, id)
        )
        conn.commit()
        conn.close()

        sync_to_supabase('Bus', 'update',
            {'Numero_bus': numero, 'Etat': etat, 'Code_chauffeur': id_chauffeur},
            {'Code_bus': id}
        )
        return jsonify({"status": "success", "message": "Bus mis à jour"}), 200
    except Exception as e:
        print(f"Erreur update_bus: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/delete_bus/<int:id>', methods=['DELETE'])
def delete_bus(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Incident WHERE Code_bus = ?', (id,))
        conn.execute('UPDATE Ligne SET Code_bus = NULL WHERE Code_bus = ?', (id,))
        conn.execute('DELETE FROM Bus WHERE Code_bus = ?', (id,))
        conn.commit()
        conn.close()

        sync_to_supabase('Incident', 'delete', match={'Code_bus': id})
        sync_to_supabase('Ligne', 'update', {'Code_bus': None}, {'Code_bus': id})
        sync_to_supabase('Bus', 'delete', match={'Code_bus': id})
        return jsonify({"status": "success", "message": "Bus supprimé"}), 200
    except Exception as e:
        print(f"Erreur delete_bus: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── LIGNES ───────────────────────────────────────────────────────
@app.route('/add_ligne', methods=['POST'])
def add_ligne():
    data = request.json
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Ligne (Libelle, Description, Code_bus) VALUES (?, ?, ?)",
            (data['libelle'], data['description'], data['code_bus'])
        )
        conn.commit()

        # ← FIX: pas de Code_Ligne (PK) dans l'insert Supabase
        sync_to_supabase('Ligne', 'insert', {
            'Libelle': data['libelle'],
            'Description': data['description'],
            'Code_bus': data['code_bus']
        })
        return jsonify({"message": "Ligne ajoutée avec succès"}), 201
    except Exception as e:
        print(f"Erreur Flask add_ligne: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/get_lignes', methods=['GET'])
def get_lignes():
    try:
        conn = get_db_connection()
        lignes = conn.execute('SELECT * FROM Ligne ORDER BY Code_Ligne DESC').fetchall()
        conn.close()
        lignes_list = [dict(row) for row in lignes]
        return jsonify(lignes_list), 200
    except Exception as e:
        print(f"Erreur get_lignes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/delete_ligne/<int:id>', methods=['DELETE'])
def delete_ligne(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Ligne WHERE Code_Ligne = ?', (id,))
        conn.commit()
        conn.close()
        sync_to_supabase('Ligne', 'delete', match={'Code_Ligne': id})
        return jsonify({"message": "Ligne supprimée"}), 200
    except Exception as e:
        print(f"Erreur delete_ligne: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/update_ligne/<int:id>', methods=['PUT', 'POST'])
def update_ligne(id):
    try:
        data = request.get_json()
        libelle = data.get('libelle') or data.get('Libelle')
        description = data.get('description') or data.get('Description')
        code_bus = data.get('code_bus') or data.get('Code_bus')

        conn = get_db_connection()
        conn.execute(
            'UPDATE Ligne SET Libelle = ?, Description = ?, Code_bus = ? WHERE Code_Ligne = ?',
            (libelle, description, code_bus, id)
        )
        conn.commit()
        conn.close()

        sync_to_supabase('Ligne', 'update',
            {'Libelle': libelle, 'Description': description, 'Code_bus': code_bus},
            {'Code_Ligne': id}
        )
        return jsonify({"message": "Ligne mise à jour"}), 200
    except Exception as e:
        print(f"Erreur update_ligne: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_all_lignes', methods=['GET'])
def get_all_lignes():
    conn = None
    try:
        conn = get_db_connection()
        query = """
            SELECT L.*, B.Numero_bus, U.Nom as Nom_Chauffeur
            FROM Ligne L
            LEFT JOIN Bus B ON L.Code_bus = B.Code_bus
            LEFT JOIN Chauffeur C ON B.Code_chauffeur = C.Code_chauffeur
            LEFT JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur
            ORDER BY L.Code_Ligne DESC
        """
        lignes = conn.execute(query).fetchall()
        result = []
        for l in lignes:
            result.append({
                "code_ligne": l["Code_Ligne"],
                "libelle": l["Libelle"] if l["Libelle"] else "Sans Nom",
                "description": l["Description"] if l["Description"] else "",
                "code_bus": l["Code_bus"],
                "nom_chauffeur": l["Nom_Chauffeur"] if l["Nom_Chauffeur"] else "Non assigné"
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()


# ─── CHAUFFEURS ───────────────────────────────────────────────────
@app.route('/get_chauffeurs', methods=['GET'])
def get_chauffeurs():
    try:
        conn = get_db_connection()
        query = """
        SELECT u.ID_utilisateur, u.Nom, u.Email, c.Code_chauffeur 
        FROM Chauffeur c
        JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
        ORDER BY c.Code_chauffeur DESC
        """
        rows = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_chauffeur', methods=['POST'])
def add_chauffeur():
    data = request.get_json()
    nom = data.get('Nom')
    email = data.get('Email')
    password = data.get('Password')

    if not nom or not email or not password:
        return jsonify({"error": "Nom, Email et Password sont obligatoires"}), 400

    conn = get_db_connection()
    try:
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        cursor = conn.execute(
            'INSERT INTO Utilisateur (Nom, Email, Mot_de_passe, Role) VALUES (?, ?, ?, ?)',
            (nom, email, hashed_pw, 'chauffeur')
        )
        user_id = cursor.lastrowid
        conn.execute('INSERT INTO Chauffeur (ID_utilisateur) VALUES (?)', (user_id,))
        conn.commit()

        # ← FIX: pas de PK dans les inserts Supabase
        sync_to_supabase('Utilisateur', 'insert', {
            'Nom': nom, 'Email': email, 'Mot_de_passe': hashed_pw, 'Role': 'chauffeur'
        })
        sync_to_supabase('Chauffeur', 'insert', {'ID_utilisateur': user_id})
        return jsonify({"message": "Chauffeur ajouté avec succès"}), 201
    except Exception as e:
        print(f"Erreur add_chauffeur: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/delete_chauffeur/<int:id>', methods=['DELETE'])
def delete_chauffeur(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Chauffeur WHERE ID_utilisateur = ?', (id,))
        conn.execute('DELETE FROM Utilisateur WHERE ID_utilisateur = ?', (id,))
        conn.commit()
        conn.close()
        sync_to_supabase('Chauffeur', 'delete', match={'ID_utilisateur': id})
        sync_to_supabase('Utilisateur', 'delete', match={'ID_utilisateur': id})
        return jsonify({"message": "Chauffeur supprimé avec succès"}), 200
    except Exception as e:
        print(f"Erreur delete_chauffeur: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/update_chauffeur/<int:id>', methods=['PUT'])
def update_chauffeur(id):
    try:
        data = request.get_json()
        nom = data.get('Nom')
        email = data.get('Email')
        password = data.get('Password')

        conn = get_db_connection()
        if password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        else:
            existing = conn.execute(
                'SELECT Mot_de_passe FROM Utilisateur WHERE ID_utilisateur = ?', (id,)
            ).fetchone()
            hashed_pw = existing['Mot_de_passe'] if existing else ''

        conn.execute(
            'UPDATE Utilisateur SET Nom = ?, Email = ?, Mot_de_passe = ? WHERE ID_utilisateur = ?',
            (nom, email, hashed_pw, id)
        )
        conn.commit()
        conn.close()

        sync_to_supabase('Utilisateur', 'update',
            {'Nom': nom, 'Email': email, 'Mot_de_passe': hashed_pw},
            {'ID_utilisateur': id}
        )
        return jsonify({"message": "Chauffeur mis à jour"}), 200
    except Exception as e:
        print(f"Erreur update_chauffeur: {e}")
        return jsonify({"error": str(e)}), 500


# ─── PROFIL ───────────────────────────────────────────────────────
@app.route('/get_profile/<email>', methods=['GET'])
def get_profile(email):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT Nom, Email, Photo FROM Utilisateur WHERE Email = ?', (email,)
    ).fetchone()
    conn.close()
    if user:
        return jsonify({"Nom": user['Nom'], "Email": user['Email'], "Photo": user['Photo']}), 200
    return jsonify({"error": "User not found"}), 404


@app.route('/update_profile', methods=['POST'])
def update_profile():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_name = data.get('name')
        new_email = data.get('email')
        new_password = data.get('password')
        new_photo = data.get('photo')

        if not user_id:
            return jsonify({"error": "User ID is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        if new_email:
            check_email = cursor.execute(
                "SELECT ID_utilisateur FROM Utilisateur WHERE Email = ? AND ID_utilisateur != ?",
                (new_email, user_id)
            ).fetchone()
            if check_email:
                conn.close()
                return jsonify({"error": "Cet email est déjà utilisé par un autre compte"}), 400

        query = "UPDATE Utilisateur SET Nom = ?, Email = ?, Photo = ?"
        params = [new_name, new_email, new_photo]

        if new_password and len(new_password) >= 6:
            hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
            query += ", Mot_de_passe = ?"
            params.append(hashed_pw)

        query += " WHERE ID_utilisateur = ?"
        params.append(user_id)
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return jsonify({"message": "Profil mis à jour avec succès"}), 200
    except Exception as e:
        print(f"Erreur update_profile: {e}")
        return jsonify({"error": str(e)}), 500


# ─── PARCOURS ─────────────────────────────────────────────────────
@app.route('/get_parcours/<int:code_ligne>', methods=['GET'])
def get_parcours_by_ligne(code_ligne):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Parcours WHERE Code_Ligne = ?", (code_ligne,))
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(ix) for ix in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_parcours', methods=['POST'])
def add_parcours():
    try:
        data = request.get_json()
        depart = data.get('Depart')
        arrivee = data.get('Arrivee')
        heure_d = data.get('Heure_depart')
        heure_a = data.get('Heure_arrivee', '--:--')
        code_ligne = data.get('Code_Ligne')

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO Parcours (Depart, Arrivee, Heure_depart, Heure_arrivee, Code_Ligne) VALUES (?, ?, ?, ?, ?)',
            (depart, arrivee, heure_d, heure_a, code_ligne)
        )
        conn.commit()
        conn.close()

        # ← FIX: pas d'ID_parcours (PK) dans l'insert
        sync_to_supabase('Parcours', 'insert', {
            'Depart': depart, 'Arrivee': arrivee,
            'Heure_depart': heure_d, 'Heure_arrivee': heure_a,
            'Code_Ligne': code_ligne
        })
        return jsonify({"message": "Success"}), 201
    except Exception as e:
        print(f"Erreur add_parcours: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/update_parcours/<int:id>', methods=['PUT', 'POST', 'OPTIONS'])
def update_parcours(id):
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200

    conn = get_db_connection()
    try:
        data = request.get_json(force=True)
        conn.execute('''
            UPDATE Parcours 
            SET Depart = ?, Arrivee = ?, Heure_depart = ?, Heure_arrivee = ?, Code_Ligne = ? 
            WHERE ID_parcours = ?
        ''', (
            data.get('Depart'), data.get('Arrivee'),
            data.get('Heure_depart'), data.get('Heure_arrivee'),
            data.get('Code_Ligne'), id
        ))
        conn.commit()

        sync_to_supabase('Parcours', 'update', {
            'Depart': data.get('Depart'), 'Arrivee': data.get('Arrivee'),
            'Heure_depart': data.get('Heure_depart'), 'Heure_arrivee': data.get('Heure_arrivee'),
            'Code_Ligne': data.get('Code_Ligne')
        }, {'ID_parcours': id})
        return jsonify({"status": "success", "message": "Mise à jour réussie"}), 200
    except Exception as e:
        print(f"UPDATE PARCOURS ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route('/get_all_parcours', methods=['GET'])
def get_all_parcours():
    try:
        conn = get_db_connection()
        query = """
            SELECT P.*, L.Libelle as Nom_Ligne
            FROM Parcours P
            JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            ORDER BY P.ID_parcours DESC
        """
        rows = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(ix) for ix in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_parcours/<int:id>', methods=['DELETE', 'OPTIONS'])
def delete_parcours(id):
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200

    conn = get_db_connection()
    try:
        cur = conn.execute('DELETE FROM Parcours WHERE ID_parcours = ?', (id,))
        conn.commit()
        if cur.rowcount > 0:
            sync_to_supabase('Parcours', 'delete', match={'ID_parcours': id})
            return jsonify({"status": "success", "message": "Suppression réussie"}), 200
        return jsonify({"status": "error", "message": "Parcours non trouvé"}), 404
    except Exception as e:
        print(f"DELETE PARCOURS ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# ─── INCIDENTS ────────────────────────────────────────────────────
@app.route('/get_incidents', methods=['GET'])
def get_incidents():
    conn = get_db_connection()
    query = '''SELECT I.*, 
                      COALESCE(B.Numero_bus, 'N/A') as Numero_bus, 
                      COALESCE(U.Nom, 'Inconnu') as NomChauffeur 
               FROM Incident I
               LEFT JOIN Bus B ON I.Code_bus = B.Code_bus
               LEFT JOIN Chauffeur C ON I.Code_chauffeur = C.Code_chauffeur
               LEFT JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur
               ORDER BY I.Date DESC'''
    items = [dict(ix) for ix in conn.execute(query).fetchall()]
    conn.close()
    return jsonify(items)


@app.route('/get_all_incidents', methods=['GET'])
def get_all_incidents():
    try:
        conn = get_db_connection()
        query = '''
            SELECT i.*, l.Libelle as Nom_Ligne, 
                   COALESCE(b1.Numero_bus, b2.Numero_bus, b3.Numero_bus, b4.Numero_bus) as Numero_bus
            FROM Incident i
            LEFT JOIN Ligne l ON i.Code_Ligne = l.Code_Ligne
            LEFT JOIN Bus b1 ON i.Code_bus = b1.Code_bus
            LEFT JOIN Bus b2 ON l.Code_bus = b2.Code_bus
            LEFT JOIN Bus b3 ON i.Code_chauffeur = b3.Code_chauffeur
            LEFT JOIN Chauffeur c_fix ON i.Code_chauffeur = c_fix.ID_utilisateur
            LEFT JOIN Bus b4 ON c_fix.Code_chauffeur = b4.Code_chauffeur
            GROUP BY i.ID_incident
            ORDER BY i.Date DESC
        '''
        incidents = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(ix) for ix in incidents])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_incident', methods=['POST'])
def add_incident():
    try:
        data = request.json
        description = data.get('description', '')
        id_chauffeur = data.get('Code_chauffeur') or data.get('code_chauffeur')
        id_ligne = data.get('Code_Ligne') or data.get('code_ligne')
        code_bus = data.get('Code_bus') or data.get('code_bus')
        statut = data.get('Statut', 'Signalé')
        date_incident = data.get('Date') or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()

        if not code_bus and id_chauffeur:
            res_bus = cursor.execute(
                "SELECT Code_bus FROM Bus WHERE Code_chauffeur = ?", (id_chauffeur,)
            ).fetchone()
            if res_bus:
                code_bus = res_bus['Code_bus']

        cursor.execute("""
            INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus, Statut) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (description, date_incident, id_chauffeur, id_ligne, code_bus, statut))
        conn.commit()
        conn.close()

        # ← FIX: pas d'ID_incident (PK) dans l'insert
        sync_to_supabase('Incident', 'insert', {
            'Description': description, 'Date': date_incident,
            'Code_chauffeur': id_chauffeur, 'Code_Ligne': id_ligne,
            'Code_bus': code_bus, 'Statut': statut
        })
        return jsonify({"message": "Incident ajouté avec succès"}), 201
    except Exception as e:
        print(f"Erreur add_incident: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/delete_incident/<int:id>', methods=['DELETE'])
def delete_incident(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Incident WHERE ID_incident = ?', (id,))
        conn.commit()
        conn.close()
        sync_to_supabase('Incident', 'delete', match={'ID_incident': id})
        return jsonify({"status": "success", "message": "Incident supprimé"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_incident_status/<int:id>', methods=['POST'])
def update_incident_status(id):
    data = request.get_json()
    statut = data.get('Statut')
    critique = data.get('Critique')
    try:
        conn = get_db_connection()
        conn.execute(
            'UPDATE Incident SET Statut = ?, Performance_IA = ? WHERE ID_incident = ?',
            (statut, critique, id)
        )
        conn.commit()
        conn.close()
        sync_to_supabase('Incident', 'update',
            {'Statut': statut, 'Performance_IA': critique},
            {'ID_incident': id}
        )
        return jsonify({"message": "Success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/declare_incident', methods=['POST', 'OPTIONS'])
def declare_incident():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    try:
        data = request.get_json()
        user_id = data.get('driver_id')
        description = data.get('description', '')
        timestamp = data.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        conn = get_db_connection()
        cursor = conn.cursor()

        res_chauffeur = cursor.execute(
            "SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res_chauffeur:
            conn.close()
            return jsonify({"error": "Chauffeur non trouvé"}), 404

        code_chauffeur = res_chauffeur['Code_chauffeur']
        res_info = cursor.execute("""
            SELECT B.Code_bus, L.Code_Ligne 
            FROM Bus B 
            LEFT JOIN Ligne L ON B.Code_bus = L.Code_bus 
            WHERE B.Code_chauffeur = ? LIMIT 1
        """, (code_chauffeur,)).fetchone()

        code_bus = res_info['Code_bus'] if res_info else None
        code_ligne = res_info['Code_Ligne'] if res_info else data.get('line_id', 1)

        cursor.execute("""
            INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus) 
            VALUES (?, ?, ?, ?, ?)
        """, (description, timestamp, code_chauffeur, code_ligne, code_bus))
        conn.commit()
        conn.close()

        # ← FIX: pas de PK dans l'insert
        sync_to_supabase('Incident', 'insert', {
            'Description': description, 'Date': timestamp,
            'Code_chauffeur': code_chauffeur, 'Code_Ligne': code_ligne,
            'Code_bus': code_bus
        })
        return jsonify({"message": "Incident signalé avec succès"}), 201
    except Exception as e:
        print(f"Erreur declare_incident: {e}")
        return jsonify({"error": str(e)}), 500


# ─── AVIS ─────────────────────────────────────────────────────────
@app.route('/add_avis', methods=['POST', 'OPTIONS'])
def add_avis():
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200

    data = request.get_json(force=True)
    comment = data.get('commentaire', '')
    note = data.get('note', 5)
    client_id = data.get('client_id') or data.get('code_client')
    parcours_id = data.get('parcours_id')
    id_historique = data.get('id_historique')

    sentiment_score = 0.0
    sentiment_label = "Neutre"
    keywords = ""
    category = "Général"
    is_risk = "Non"

    if HAS_GEMINI and GEMINI_API_KEY != "VOTRE_CLE_API_ICI" and comment:
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            prompt = f"""
            Analyse ce commentaire de transport public (en Français ou Derja Tunisienne) :
            "{comment}"
            Réponds uniquement en JSON avec ces champs exacts :
            {{
              "sentiment": "Positif" | "Négatif" | "Neutre",
              "score": float entre -1.0 et 1.0,
              "category": "Chauffeur" | "Confort" | "Véhicule" | "Service" | "Sécurité",
              "keywords": "mot1, mot2, ...",
              "risk": "Oui" | "Non"
            }}
            """
            response = model.generate_content(prompt)
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            ai_data = json.loads(res_text)
            sentiment_label = ai_data.get("sentiment", "Neutre")
            sentiment_score = float(ai_data.get("score", 0.0))
            category = ai_data.get("category", "Général")
            keywords = ai_data.get("keywords", "")
            is_risk = ai_data.get("risk", "Non")
        except Exception as e:
            print(f"Erreur Gemini: {e}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        true_client_id = None
        if client_id:
            res_client = cursor.execute(
                "SELECT Code_client FROM Client WHERE ID_utilisateur = ?", (client_id,)
            ).fetchone()
            if res_client:
                true_client_id = res_client['Code_client']
            else:
                cursor.execute("INSERT INTO Client (ID_utilisateur) VALUES (?)", (client_id,))
                true_client_id = cursor.lastrowid
                sync_to_supabase('Client', 'insert', {'ID_utilisateur': client_id})

        code_chauffeur = None
        code_ligne = None
        code_bus = None

        if id_historique:
            res = cursor.execute("""
                SELECT H.Code_chauffeur, H.ID_parcours, P.Code_Ligne, L.Code_bus
                FROM Historique H
                JOIN Parcours P ON H.ID_parcours = P.ID_parcours
                LEFT JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
                WHERE H.ID_historique = ?
            """, (id_historique,)).fetchone()
            if res:
                code_chauffeur = res['Code_chauffeur']
                parcours_id = res['ID_parcours']
                code_ligne = res['Code_Ligne']
                code_bus = res['Code_bus']

        if not code_bus and code_chauffeur:
            res_bus = cursor.execute(
                "SELECT Code_bus FROM Bus WHERE Code_chauffeur = ?", (code_chauffeur,)
            ).fetchone()
            if res_bus: code_bus = res_bus['Code_bus']

        if not code_bus and code_ligne:
            res_bus = cursor.execute(
                "SELECT Code_bus FROM Ligne WHERE Code_Ligne = ?", (code_ligne,)
            ).fetchone()
            if res_bus: code_bus = res_bus['Code_bus']

        date_avis = data.get('date', datetime.now().strftime("%Y-%m-%d"))
        cursor.execute("""
            INSERT INTO Avis 
            (Code_client, ID_historique, ID_parcours, Note, Commentaire, 
             Sentiment_score, Sentiment_label, Keywords, Category, Date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (true_client_id, id_historique, parcours_id, note, comment,
              sentiment_score, sentiment_label, keywords, category, date_avis))
        new_avis_id = cursor.lastrowid

        if code_chauffeur:
            cursor.execute("""
                UPDATE Chauffeur 
                SET Performance_score = (
                    SELECT (AVG(Note) + AVG(Sentiment_score)*0.5) 
                    FROM Avis A
                    LEFT JOIN Historique H ON A.ID_historique = H.ID_historique
                    LEFT JOIN Parcours P ON A.ID_parcours = P.ID_parcours
                    LEFT JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
                    LEFT JOIN Bus B ON L.Code_bus = B.Code_bus
                    WHERE H.Code_chauffeur = ? OR B.Code_chauffeur = ?
                )
                WHERE Code_chauffeur = ?
            """, (code_chauffeur, code_chauffeur, code_chauffeur))

            if id_historique:
                cursor.execute("""
                    UPDATE Historique 
                    SET Performance_IA = (
                        SELECT (AVG(Note) * 20)
                        FROM Avis WHERE ID_historique = ?
                    )
                    WHERE ID_historique = ?
                """, (id_historique, id_historique))

        incident_id = None
        date_incident = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if is_risk == "Oui":
            cursor.execute("""
                INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus)
                VALUES (?, ?, ?, ?, ?)
            """, (f"[IA ALERT] {comment}", date_incident, code_chauffeur, code_ligne, code_bus))
            incident_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # ← FIX: pas de PK dans les inserts Supabase
        sync_to_supabase('Avis', 'insert', {
            'Code_client': true_client_id, 'ID_historique': id_historique,
            'ID_parcours': parcours_id, 'Note': note, 'Commentaire': comment,
            'Sentiment_score': sentiment_score, 'Sentiment_label': sentiment_label,
            'Keywords': keywords, 'Category': category, 'Date': date_avis
        })
        if is_risk == "Oui" and incident_id:
            sync_to_supabase('Incident', 'insert', {
                'Description': f"[IA ALERT] {comment}", 'Date': date_incident,
                'Code_chauffeur': code_chauffeur, 'Code_Ligne': code_ligne,
                'Code_bus': code_bus, 'Statut': 'Signalé'
            })

        return jsonify({
            "status": "success",
            "ai_analysis": {
                "score": sentiment_score,
                "label": sentiment_label,
                "keywords": keywords
            }
        }), 201
    except Exception as e:
        print(f"Erreur add_avis: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_avis', methods=['GET'])
def get_avis():
    try:
        conn = get_db_connection()
        query = '''
            SELECT a.*,
                   COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            ORDER BY a.Date DESC
        '''
        avis = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(row) for row in avis]), 200
    except Exception as e:
        print(f"Erreur get_avis: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_avis_by_client/<int:client_id>', methods=['GET'])
def get_avis_by_client(client_id):
    try:
        conn = get_db_connection()
        avis = conn.execute("""
            SELECT a.ID_avis, a.Commentaire, a.Note, a.Date, h.Depart, h.Arrivee
            FROM Avis a
            JOIN Historique h ON a.ID_historique = h.ID_historique
            WHERE a.Code_client = ?
            ORDER BY a.Date DESC
        """, (client_id,)).fetchall()
        conn.close()
        return jsonify([dict(row) for row in avis]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update_avis/<int:id>', methods=['PUT'])
def update_avis(id):
    try:
        data = request.get_json()
        commentaire = data.get("commentaire")
        note = data.get("note")
        conn = get_db_connection()
        conn.execute(
            "UPDATE Avis SET Commentaire = ?, Note = ? WHERE ID_avis = ?",
            (commentaire, note, id)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_avis/<int:id>', methods=['DELETE'])
def delete_avis(id):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM Avis WHERE ID_avis = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify({"message": "deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── DRIVER ENDPOINTS ─────────────────────────────────────────────
@app.route('/get_driver_reviews/<int:user_id>', methods=['GET'])
def get_driver_reviews(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        res = cursor.execute(
            "SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res:
            conn.close()
            return jsonify([]), 200
        code_chauffeur = res['Code_chauffeur']
        query = """
            SELECT A.Commentaire as commentaire, A.Note as note, 
                   A.Sentiment_label as sentiment, A.Category as category, A.Date as date
            FROM Avis A
            LEFT JOIN Historique H ON A.ID_historique = H.ID_historique
            LEFT JOIN Parcours P ON A.ID_parcours = P.ID_parcours
            LEFT JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            LEFT JOIN Bus B ON L.Code_bus = B.Code_bus
            WHERE H.Code_chauffeur = ? OR B.Code_chauffeur = ?
            ORDER BY A.Date DESC
        """
        cursor.execute(query, (code_chauffeur, code_chauffeur))
        reviews = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(reviews), 200
    except Exception as e:
        print(f"Error get_driver_reviews: {e}")
        return jsonify([]), 200


@app.route('/get_driver_stats/<int:user_id>', methods=['GET'])
def get_driver_stats(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        res = cursor.execute(
            "SELECT Code_chauffeur, Performance_score FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res:
            return jsonify({"error": "Chauffeur non trouvé"}), 404
        code_chauffeur = res['Code_chauffeur']
        perf_score = res['Performance_score']
        query = """
            SELECT a.Note, a.Commentaire, a.Sentiment_label, a.Category, a.Date
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            LEFT JOIN Parcours p ON a.ID_parcours = p.ID_parcours
            LEFT JOIN Ligne l ON p.Code_Ligne = l.Code_Ligne
            LEFT JOIN Bus b ON l.Code_bus = b.Code_bus
            WHERE h.Code_chauffeur = ? OR b.Code_chauffeur = ?
            ORDER BY a.Date DESC LIMIT 5
        """
        avis = cursor.execute(query, (code_chauffeur, code_chauffeur)).fetchall()
        cat_stats = cursor.execute("""
            SELECT Category, COUNT(*) as count 
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            LEFT JOIN Parcours p ON a.ID_parcours = p.ID_parcours
            LEFT JOIN Ligne l ON p.Code_Ligne = l.Code_Ligne
            LEFT JOIN Bus b ON l.Code_bus = b.Code_bus
            WHERE h.Code_chauffeur = ? OR b.Code_chauffeur = ?
            GROUP BY Category
        """, (code_chauffeur, code_chauffeur)).fetchall()
        incident_count = cursor.execute(
            "SELECT COUNT(*) FROM Incident WHERE Code_chauffeur = ?", (code_chauffeur,)
        ).fetchone()[0]
        conn.close()
        return jsonify({
            "performance_score": round(perf_score, 2),
            "incident_count": incident_count,
            "recent_reviews": [dict(row) for row in avis],
            "category_distribution": {row['Category']: row['count'] for row in cat_stats}
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_my_assignment/<int:user_id>', methods=['GET'])
def get_my_assignment(user_id):
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        query = """
            SELECT DISTINCT
                p.ID_parcours, 
                COALESCE(p.Depart, '---') as Depart,
                COALESCE(p.Arrivee, '---') as Arrivee,
                COALESCE(p.Heure_depart, '--:--') as Heure_depart, 
                COALESCE(p.Heure_arrivee, '--:--') as Heure_arrivee, 
                Ligne.Libelle,
                COALESCE(
                    (SELECT Statut FROM Historique 
                     WHERE ID_parcours = p.ID_parcours 
                     AND Code_chauffeur = Chauffeur.Code_chauffeur 
                     AND Date LIKE ? 
                     ORDER BY ID_historique DESC LIMIT 1), 
                    'Pas démarré'
                ) as Statut
            FROM Chauffeur
            JOIN Bus ON Chauffeur.Code_chauffeur = Bus.Code_chauffeur
            JOIN Ligne ON Bus.Code_bus = Ligne.Code_bus
            LEFT JOIN Parcours p ON Ligne.Code_Ligne = p.Code_Ligne
            WHERE Chauffeur.ID_utilisateur = ?
            ORDER BY Ligne.Libelle, p.Heure_depart ASC
        """
        cursor.execute(query, (f"{today}%", user_id))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        conn.close()
        return jsonify(results), 200
    except Exception as e:
        print(f"Erreur get_my_assignment: {e}")
        return jsonify([]), 500


@app.route('/log_historique', methods=['POST'])
def log_historique():
    try:
        data = request.get_json()
        action = data['action']
        user_id = data['driver_id']
        parcours_id = data['parcours_id']
        now = data['timestamp']

        conn = get_db_connection()
        cursor = conn.cursor()

        res_chauffeur = cursor.execute(
            "SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)
        ).fetchone()
        if not res_chauffeur:
            conn.close()
            return jsonify({"error": "Chauffeur non trouvé"}), 404
        code_chauffeur = res_chauffeur['Code_chauffeur']

        if action == "Début":
            cursor.execute("""
                INSERT INTO Historique (Date, Heure_fin, Statut, Depart, Arrivee, Performance_IA, ID_parcours, Code_chauffeur) 
                VALUES (?, NULL, 'En cours', ?, ?, NULL, ?, ?)
            """, (now, data.get('depart'), data.get('arrivee'), parcours_id, code_chauffeur))
            message = "Voyage démarré"
        elif action == "Fin":
            cursor.execute("""
                UPDATE Historique 
                SET Heure_fin = ?, Statut = 'Terminé', Performance_IA = 100.0 
                WHERE Code_chauffeur = ? AND ID_parcours = ? AND Statut = 'En cours'
            """, (now, code_chauffeur, parcours_id))
            if cursor.rowcount == 0:
                cursor.execute("""
                    UPDATE Historique 
                    SET Heure_fin = ?, Statut = 'Terminé', Performance_IA = 100.0 
                    WHERE Code_chauffeur = ? AND ID_parcours = ? AND Heure_fin IS NULL
                """, (now, code_chauffeur, parcours_id))
            message = "Voyage terminé"

        conn.commit()
        conn.close()
        return jsonify({"message": message}), 201
    except Exception as e:
        print(f"Erreur log_historique: {e}")
        return jsonify({"error": str(e)}), 500


# ─── STATS & RAPPORTS ─────────────────────────────────────────────
@app.route('/get_counts', methods=['GET'])
def get_counts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        lignes = cursor.execute('SELECT COUNT(*) FROM Ligne').fetchone()[0]
        chauffeurs = cursor.execute('SELECT COUNT(*) FROM Chauffeur').fetchone()[0]
        bus = cursor.execute('SELECT COUNT(*) FROM Bus').fetchone()[0]
        incidents = cursor.execute('SELECT COUNT(*) FROM Incident').fetchone()[0]
        conn.close()
        return jsonify({
            "lignes": lignes, "chauffeurs": chauffeurs,
            "bus": bus, "incidents": incidents
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_performance_v2', methods=['GET'])
def get_performance_v2():
    conn = get_db_connection()
    try:
        query = '''
            SELECT U.Nom as Nom_Chauffeur,
                   COUNT(*) as Total_Avis,
                   AVG(A.Note) as Average_Note
            FROM Avis A
            JOIN Parcours P ON A.ID_parcours = P.ID_parcours
            JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            JOIN Bus B ON L.Code_bus = B.Code_bus
            JOIN Chauffeur C ON B.Code_chauffeur = C.Code_chauffeur
            JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur
            GROUP BY C.Code_chauffeur
        '''
        rows = conn.execute(query).fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/get_nlp_report', methods=['GET'])
def get_nlp_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        total_avis = cursor.execute("SELECT COUNT(*) FROM Avis").fetchone()[0]
        sentiments = cursor.execute(
            "SELECT Sentiment_label, COUNT(*) as count FROM Avis GROUP BY Sentiment_label"
        ).fetchall()
        sentiment_stats = {row['Sentiment_label']: row['count'] for row in sentiments}
        avg_score = cursor.execute("SELECT AVG(Sentiment_score) FROM Avis").fetchone()[0] or 0
        all_keywords = cursor.execute("SELECT Keywords FROM Avis WHERE Keywords != ''").fetchall()
        keyword_counts = {}
        for row in all_keywords:
            if row['Keywords']:
                for kw in row['Keywords'].split(", "):
                    kw = kw.strip()
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_drivers = cursor.execute("""
            SELECT u.Nom, AVG(a.Sentiment_score) as avg_sentiment, COUNT(a.ID_avis) as nb_avis
            FROM Avis a
            JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            GROUP BY c.Code_chauffeur
            ORDER BY avg_sentiment DESC LIMIT 3
        """).fetchall()
        parcours_stats = cursor.execute("""
            SELECT p.ID_parcours, p.Depart, p.Arrivee, AVG(a.Sentiment_score) as avg_sentiment, COUNT(a.ID_avis) as nb_avis
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Parcours p ON (a.ID_parcours = p.ID_parcours OR (a.ID_parcours IS NULL AND h.ID_parcours = p.ID_parcours))
            GROUP BY p.ID_parcours
            ORDER BY avg_sentiment DESC
        """).fetchall()
        safety_alerts = cursor.execute(
            "SELECT COUNT(*) FROM Incident WHERE Description LIKE '[IA ALERT]%'"
        ).fetchone()[0]
        conn.close()
        return jsonify({
            "total_avis": total_avis,
            "sentiment_distribution": sentiment_stats,
            "average_sentiment_score": round(avg_score, 2),
            "top_keywords": sorted_keywords,
            "top_drivers": [dict(row) for row in top_drivers],
            "parcours_stats": [dict(row) for row in parcours_stats],
            "safety_alerts_count": safety_alerts
        }), 200
    except Exception as e:
        print(f"Erreur rapport NLP: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_driver_nlp_report', methods=['GET'])
def get_driver_nlp_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM Avis WHERE Category = 'Chauffeur'").fetchone()[0]
        sentiments = cursor.execute("""
            SELECT Sentiment_label, COUNT(*) as count
            FROM Avis WHERE Category = 'Chauffeur'
            GROUP BY Sentiment_label
        """).fetchall()
        sentiment_dist = {r['Sentiment_label']: r['count'] for r in sentiments}
        avg_score = cursor.execute(
            "SELECT AVG(Sentiment_score) FROM Avis WHERE Category = 'Chauffeur'"
        ).fetchone()[0] or 0
        avg_note = cursor.execute(
            "SELECT AVG(Note) FROM Avis WHERE Category = 'Chauffeur'"
        ).fetchone()[0] or 0
        kw_rows = cursor.execute(
            "SELECT Keywords FROM Avis WHERE Category = 'Chauffeur' AND Keywords != ''"
        ).fetchall()
        kw_counts = {}
        for r in kw_rows:
            if r['Keywords']:
                for kw in r['Keywords'].split(', '):
                    kw = kw.strip()
                    if kw: kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_keywords = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        avis_rows = cursor.execute("""
            SELECT a.*, COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.Category = 'Chauffeur'
            ORDER BY a.Date DESC
        """).fetchall()
        top_drivers = cursor.execute("""
            SELECT u.Nom, AVG(a.Sentiment_score) as avg_sentiment, COUNT(*) as nb_avis
            FROM Avis a
            JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.Category = 'Chauffeur'
            GROUP BY c.Code_chauffeur
            ORDER BY avg_sentiment DESC
        """).fetchall()
        conn.close()
        satisfaction_pct = round(((avg_score + 1) / 2) * 100, 1)
        return jsonify({
            "total_avis_chauffeur": total,
            "satisfaction_chauffeur": satisfaction_pct,
            "avg_note": round(avg_note, 2),
            "avg_sentiment_score": round(avg_score, 2),
            "sentiment_distribution": sentiment_dist,
            "top_keywords": top_keywords,
            "top_drivers": [dict(r) for r in top_drivers],
            "avis_list": [dict(r) for r in avis_rows]
        }), 200
    except Exception as e:
        print(f"Erreur get_driver_nlp_report: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_all_historique', methods=['GET'])
def get_all_historique():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT h.ID_historique, h.Date, h.Heure_fin, h.Statut, h.Depart, h.Arrivee, 
                   h.Performance_IA, u.Nom as Nom_Chauffeur, l.Libelle as Nom_Ligne
            FROM Historique h
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            LEFT JOIN Parcours p ON h.ID_parcours = p.ID_parcours
            LEFT JOIN Ligne l ON p.Code_Ligne = l.Code_Ligne
            ORDER BY h.Date DESC
        """
        rows = cursor.execute(query).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        print(f"Erreur get_all_historique: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_client_trips', methods=['GET'])
def get_client_trips():
    try:
        conn = get_db_connection()
        lignes = conn.execute("SELECT * FROM Ligne").fetchall()
        result = []
        for l in lignes:
            query_hist = """
                SELECT h.ID_historique, h.Date, h.Depart, h.Arrivee, u.Nom as Nom_Chauffeur
                FROM Historique h
                JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
                JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
                JOIN Parcours p ON h.ID_parcours = p.ID_parcours
                WHERE p.Code_Ligne = ?
                ORDER BY h.Date DESC
            """
            rides = conn.execute(query_hist, (l['Code_Ligne'],)).fetchall()
            result.append({
                "code_ligne": l["Code_Ligne"],
                "libelle": l["Libelle"] or "Ligne",
                "description": l["Description"] or "",
                "rides": [dict(r) for r in rides]
            })
        conn.close()
        return jsonify(result), 200
    except Exception as e:
        print(f"Erreur get_client_trips: {e}")
        return jsonify([]), 500


@app.route('/get_parcours_reviews/<int:parcours_id>', methods=['GET'])
def get_parcours_reviews(parcours_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT a.Note, a.Commentaire, a.Sentiment_label, a.Category, a.Date, 
                   COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.ID_parcours = ? OR h.ID_parcours = ?
            ORDER BY a.Date DESC
        """
        avis = cursor.execute(query, (parcours_id, parcours_id)).fetchall()
        conn.close()
        return jsonify([dict(row) for row in avis]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/assign_work', methods=['POST'])
def assign_work():
    data = request.json
    code_chauffeur = data.get('code_chauffeur')
    code_bus = data.get('code_bus')
    code_ligne = data.get('code_ligne')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Bus SET Code_chauffeur = ? WHERE Code_bus = ?", (code_chauffeur, code_bus))
        cursor.execute("UPDATE Ligne SET Code_bus = ? WHERE Code_Ligne = ?", (code_bus, code_ligne))
        conn.commit()
        return jsonify({"message": "Affectation réussie !"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/finish_parcours/<int:id_p>', methods=['PUT'])
def finish_parcours(id_p):
    conn = get_db_connection()
    try:
        heure_arrivee = datetime.now().strftime("%H:%M")
        conn.execute(
            "UPDATE Parcours SET Heure_arrivee = ?, statut = 'Terminé' WHERE ID_parcours = ?",
            (heure_arrivee, id_p)
        )
        conn.commit()
        return jsonify({"status": "success", "heure_arrivee": heure_arrivee}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route('/manage_parcours', methods=['POST'])
def manage_parcours():
    try:
        data = request.json
        action = data.get('action')
        p_depart = data.get('Depart', '---')
        p_arrivee = data.get('Arrivee', '---')
        p_heure = data.get('Heure_depart', datetime.now().strftime("%H:%M"))
        p_ligne = data.get('Code_Ligne', 1)

        conn = get_db_connection()
        cursor = conn.cursor()

        if action == 'start':
            cursor.execute("""
                INSERT INTO Parcours (Depart, Arrivee, Heure_depart, Heure_arrivee, Code_Ligne) 
                VALUES (?, ?, ?, '--:--', ?)
            """, (p_depart, p_arrivee, p_heure, p_ligne))
            conn.commit()
            msg = "Parcours démarré"
        elif action == 'end':
            heure_arrivee_str = datetime.now().strftime("%H:%M")
            cursor.execute("""
                UPDATE Parcours 
                SET Heure_arrivee = ? 
                WHERE Code_Ligne = ? AND (Heure_arrivee = '--:--' OR Heure_arrivee IS NULL)
            """, (heure_arrivee_str, p_ligne))
            conn.commit()
            msg = f"Parcours terminé à {heure_arrivee_str}"

        conn.close()
        return jsonify({"status": "success", "message": msg}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── NLP Recatégorisation ─────────────────────────────────────────
DRIVER_KEYWORDS = ['chauffeur', 'conducteur', 'pilote', 'chafer', 'impoli', 'poli',
    'grossier', 'aimable', 'sympa', 'agressif', 'comportement', 'conduite',
    'vitesse', 'rapide', 'lent', 'freinage', 'respectueux', 'courtois']
COMFORT_KEYWORDS = ['confort', 'siege', 'clim', 'climatisation', 'chaud', 'froid', 'propre', 'sale', 'bruit']
VEHICLE_KEYWORDS = ['bus', 'vehicule', 'panne', 'vieux', 'neuf', 'voiture', 'car', 'moteur']
SERVICE_KEYWORDS = ['retard', 'heure', 'temps', 'attente', 'horaire', 'ponctuel', 'regularite', 'trajet']

def categorize_comment(comment):
    c = comment.lower()
    if any(w in c for w in DRIVER_KEYWORDS): return 'Chauffeur'
    elif any(w in c for w in COMFORT_KEYWORDS): return 'Confort'
    elif any(w in c for w in VEHICLE_KEYWORDS): return 'Véhicule'
    elif any(w in c for w in SERVICE_KEYWORDS): return 'Service'
    return 'Général'


@app.route('/recategorize_avis', methods=['POST'])
def recategorize_avis():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT ID_avis, Commentaire FROM Avis WHERE Commentaire IS NOT NULL AND Commentaire != ''"
        ).fetchall()
        updated = 0
        for row in rows:
            new_cat = categorize_comment(row['Commentaire'])
            cursor.execute("UPDATE Avis SET Category = ? WHERE ID_avis = ?", (new_cat, row['ID_avis']))
            updated += 1
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "updated": updated}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_my_reviews/<int:id_chauffeur>', methods=['GET'])
def get_my_reviews(id_chauffeur):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT note, commentaire, date, Sentiment_score 
            FROM Avis 
            WHERE ID_historique IN (SELECT ID_historique FROM Historique WHERE Code_chauffeur = ?)
            ORDER BY ID_avis DESC
        """
        cursor.execute(query, (id_chauffeur,))
        rows = cursor.fetchall()
        reviews = []
        for row in rows:
            reviews.append({
                "commentaire": row['Commentaire'] if row['Commentaire'] else "Pas de commentaire",
                "note": row['Note'],
                "sentiment": row['Sentiment_score'] if row['Sentiment_score'] else "Neutre",
                "date": row['Date']
            })
        conn.close()
        return jsonify(reviews), 200
    except Exception as e:
        print(f"Erreur get_my_reviews: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/test', methods=['GET', 'POST'])
def test():
    return jsonify({"message": "Le serveur fonctionne !"})


# ─── Lancement ────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        init_all_tables()
        print("Database initialisée avec succès !")
    except Exception as e:
        print(f"Erreur init DB: {e}")

    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=False)