# بدلت الاسم من Client لـ Supabase_Tool
from postgrest import SyncPostgrestClient

import os # تأكدي إنك عملتي import لـ os

# اقرأي القيم من Render
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# تأكدي إنهم موش فارغين (لو السيرفر طاح، هذا السطر يوريك وين الغلطة)
if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: Variables are empty!")

# للتأكد من أنها موجودة
if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Variables are empty!") # هذا سيظهر في الـ Logs
else:
    print("Success: Variables loaded!") # هذا سيظهر في الـ Logs
print(f"DEBUG: URL is {SUPABASE_URL}")
print(f"DEBUG: Key is {SUPABASE_KEY}") # هذا باش يوريك هل السيرفر شافهم أو لا
# الـ Connection
supabase = SyncPostgrestClient(f"{SUPABASE_URL}/rest/v1", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import re
from flask_bcrypt import Bcrypt
from datetime import datetime
import random
import string
from flask_mail import Mail, Message
# ─── NLP & Gemini AI Libraries ──────────────────────────────────────────────
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

# ⭐ CONFIGURATION GEMINI API ⭐
try:
    import google.generativeai as genai
    import json
    # Remplacez par votre clé gratuite de https://aistudio.google.com/
    GEMINI_API_KEY = "AIzaSyAs1JV2C1hVXZbQAyrCPi3PMY2NNIAWylA"
    genai.configure(api_key=GEMINI_API_KEY)
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False



app = Flask(__name__)
# ⭐ Smart-Trans API Configuration ⭐
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

# ⭐ CONFIGURATION FLASK-MAIL (GMAIL) ⭐
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'khawlabenhmid2@gmail.com' 
app.config['MAIL_PASSWORD'] = 'sztw sklu nyav ypzz' 
app.config['MAIL_DEFAULT_SENDER'] = 'khawlabenhmid2@gmail.com'
mail = Mail(app)


def get_db_connection():
    conn = sqlite3.connect('smart_trans.db') # اسم واحد وموحد
    conn.row_factory = sqlite3.Row
    return conn
   


def init_all_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    # تفعيل الروابط بين الجداول (مهم جداً للـ PFE)
    cursor.execute("PRAGMA foreign_keys = ON")

    # Mise à jour de la table Incident pour inclure Performance_IA et Code_bus si besoin
    try:
        cursor.execute("ALTER TABLE Incident ADD COLUMN Performance_IA FLOAT")
    except: pass
    try:
        cursor.execute("ALTER TABLE Incident ADD COLUMN Statut TEXT DEFAULT 'Signalé'")
    except: pass
    try:
        cursor.execute("ALTER TABLE Incident ADD COLUMN Code_bus INTEGER")
    except: pass

    # Correction des anciens incidents sans Code_bus (Correction automatique robuste)
    try:
        # 1. Essayer via la ligne
        cursor.execute("""
            UPDATE Incident 
            SET Code_bus = (SELECT Code_bus FROM Ligne WHERE Ligne.Code_Ligne = Incident.Code_Ligne)
            WHERE Code_bus IS NULL OR Code_bus NOT IN (SELECT Code_bus FROM Bus)
        """)
        # 2. Essayer via le chauffeur
        cursor.execute("""
            UPDATE Incident 
            SET Code_bus = (SELECT Code_bus FROM Bus WHERE Bus.Code_chauffeur = Incident.Code_chauffeur LIMIT 1)
            WHERE Code_bus IS NULL OR Code_bus NOT IN (SELECT Code_bus FROM Bus)
        """)
        # 3. Nettoyage final : supprimer les incidents orphelins (bus supprimé précédemment)
        cursor.execute("DELETE FROM Incident WHERE Code_bus IS NOT NULL AND Code_bus NOT IN (SELECT Code_bus FROM Bus)")
    except: pass

    # 1. Utilisateur (الجدول الأم)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Utilisateur (
        ID_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
        Nom TEXT,
        Email TEXT UNIQUE,
        Mot_de_passe TEXT,
        Role TEXT,
        Photo TEXT)''')

    # 2. Chauffeur (Spécialisation)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Chauffeur (
        Code_chauffeur INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        Performance_score FLOAT DEFAULT 5.0,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    # 3. Client (Spécialisation)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Client (
        Code_client INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    # 4. Administrateur (Spécialisation)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Administrateur (
        Code_administrateur INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_utilisateur INTEGER,
        FOREIGN KEY(ID_utilisateur) REFERENCES Utilisateur(ID_utilisateur) ON DELETE CASCADE)''')

    # 5. Bus
    cursor.execute('''CREATE TABLE IF NOT EXISTS Bus (
        Code_bus INTEGER PRIMARY KEY AUTOINCREMENT,
        Numero_bus TEXT UNIQUE,
        Etat TEXT,
        Code_chauffeur INTEGER,
        FOREIGN KEY (Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur) ON DELETE SET NULL)''')

    # 6. Ligne
    cursor.execute('''CREATE TABLE IF NOT EXISTS Ligne (
        Code_Ligne INTEGER PRIMARY KEY AUTOINCREMENT,
        Libelle TEXT,
        Description TEXT,
        Code_bus INTEGER,
        FOREIGN KEY(Code_bus) REFERENCES Bus(Code_bus))''')

    # 7. Parcours
    cursor.execute('''CREATE TABLE IF NOT EXISTS Parcours (
        ID_parcours INTEGER PRIMARY KEY AUTOINCREMENT,
        Depart TEXT,
        Arrivee TEXT,
        Heure_depart TEXT,
        Heure_arrivee TEXT,
        Code_Ligne INTEGER,
        FOREIGN KEY(Code_Ligne) REFERENCES Ligne(Code_Ligne))''')

    # 8. Historique (Suivi dynamique des trajets)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Historique (
        ID_historique INTEGER PRIMARY KEY AUTOINCREMENT,
        Date TEXT,
        Heure_fin TEXT,
        Statut TEXT,
        Depart TEXT,
        Arrivee TEXT,
        Performance_IA FLOAT,
        ID_parcours INTEGER,
        Code_chauffeur INTEGER,
        FOREIGN KEY(ID_parcours) REFERENCES Parcours(ID_parcours),
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur))''')

    # 9. Incident
    cursor.execute('''CREATE TABLE IF NOT EXISTS Incident (
        ID_incident INTEGER PRIMARY KEY AUTOINCREMENT,
        Description TEXT,
        Date TEXT,
        Code_chauffeur INTEGER,
        Code_Ligne INTEGER,
        FOREIGN KEY(Code_chauffeur) REFERENCES Chauffeur(Code_chauffeur),
        FOREIGN KEY(Code_Ligne) REFERENCES Ligne(Code_Ligne))''')

    # 10. Avis (Enrichi pour l'IA)
    cursor.execute('''CREATE TABLE IF NOT EXISTS Avis (
        ID_avis INTEGER PRIMARY KEY AUTOINCREMENT,
        Code_client INTEGER,
        ID_historique INTEGER,
        Note INTEGER,
        Commentaire TEXT,
        Date TEXT,
        Sentiment_score FLOAT,
        Sentiment_label TEXT,
        Keywords TEXT,
        Category TEXT,
        ID_parcours INTEGER,
        FOREIGN KEY(Code_client) REFERENCES Client(Code_client),
        FOREIGN KEY(ID_historique) REFERENCES Historique(ID_historique),
        FOREIGN KEY(ID_parcours) REFERENCES Parcours(ID_parcours))''')

    # 11. ResetCode (For Forgot Password)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ResetCode (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Email TEXT,
        Code TEXT,
        Expiration DATETIME)''')

    # إضافة Admin تجريبي
    hashed_pw = bcrypt.generate_password_hash('123456').decode('utf-8')
    cursor.execute('''INSERT OR IGNORE INTO Utilisateur (Nom, Email, Mot_de_passe, Role) 
                      VALUES (?, ?, ?, ?)''', ('Khawla', 'khawla@email.com', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()
    print("OK: Les 10 tables sont creees avec succes !")
    

    # 1. طريق التسجيل (Register)
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    nom = data.get('nom')
    email = data.get('email').lower().strip()
    password = data.get('password')

    # 🔐 التشفير بـ Bcrypt (لازم تكوني معرفة bcrypt = Bcrypt(app) الفوق)
    hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # التثبت من الإيميل
        check = cursor.execute("SELECT * FROM Utilisateur WHERE Email = ?", (email,)).fetchone()
        if check:
            conn.close()
            return jsonify({"message": "Email déjà utilisé"}), 400

        cursor.execute(
            "INSERT INTO Utilisateur (Nom, Email, Mot_de_passe, Role) VALUES (?, ?, ?, ?)",
            (nom, email, hashed_pw, 'client')
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Compte créé"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500



    
@app.route('/login', methods=['POST'])
def login():
    try:
        # 1. استقبال البيانات
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        email = data.get('email')
        password = data.get('password')

        # 2. التحقق من وجود المدخلات
        if not email or not password:
            return jsonify({"error": "Missing email or password"}), 400

        # 3. الاتصال بقاعدة البيانات
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 4. البحث عن المستخدم
        cursor.execute("SELECT * FROM Utilisateur WHERE Email = ?", (email,))
        user = cursor.fetchone()
        
        if user:
            # هنا نفترض أن الباسوورد مشفر في قاعدة البيانات
            # تأكدي من ترتيب الأعمدة في الجدول (غالباً user[2] هو الباسوورد)
            stored_password = user[3] 
            
            # التحقق من الباسوورد (باستخدام bcrypt)
            if bcrypt.check_password_hash(stored_password, password):
                conn.close()
                return jsonify({"message": "Login successful", "user": user[0]}), 200
            else:
                conn.close()
                return jsonify({"error": "Invalid password"}), 401
        else:
            conn.close()
            return jsonify({"error": "User not found"}), 404

    except Exception as e:
        # هذا السطر سيطبع الخطأ الحقيقي في الـ Logs في Render
        print("ERROR DETECTED IN LOGIN:", str(e))
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500




# 🔑 --- FORGOT PASSWORD SECTION --- 🔑

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

    # Generer un code de 6 chiffres
    code = ''.join(random.choices(string.digits, k=6))
    
    # Enregistrer le code dans la DB
    conn.execute('DELETE FROM ResetCode WHERE Email = ?', (email,)) # Supprimer les anciens codes
    conn.execute('INSERT INTO ResetCode (Email, Code) VALUES (?, ?)', (email, code))
    conn.commit()
    conn.close()

    print(f"--- DEBUG FORGOT PASSWORD ---")
    print(f"Email: {email}")
    print(f"Code genere: {code}")
    print(f"-----------------------------")

    # Envoyer l'email (Version Premium HTML)
    try:
        msg = Message("Code de vérification SMART-TRANS",
                      recipients=[email]) # <-- C'est ici que l'email devient DYNAMIQUE
        
        msg.html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="color: #008080; margin: 0;">SMART-TRANS</h1>
                <p style="color: #666; font-size: 12px;">Cyber Security Edition 2026</p>
            </div>
            
            <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; text-align: center;">
                <p style="font-size: 16px; color: #333;">Bonjour <strong>{user['Nom']}</strong>,</p>
                <p style="font-size: 14px; color: #555;">Vous avez demandé la réinitialisation de votre mot de passe. Voici votre code de vérification :</p>
                
                <div style="background: #008080; color: white; font-size: 32px; font-weight: bold; padding: 15px; border-radius: 8px; display: inline-block; letter-spacing: 5px; margin: 20px 0;">
                    {code}
                </div>
                
                <p style="font-size: 12px; color: #888;">Ce code est valable pendant 15 minutes. Ne le partagez avec personne.</p>
            </div>
            
            <div style="margin-top: 30px; text-align: center; border-top: 1px solid #eee; padding-top: 20px;">
                <p style="font-size: 12px; color: #aaa;">Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email en toute sécurité.</p>
                <p style="font-size: 14px; color: #008080; font-weight: bold;">L'équipe SMART-TRANS</p>
            </div>
        </div>
        """
        mail.send(msg)
        return jsonify({"message": "Code envoyé par email"}), 200
    except Exception as e:
        print(f"Error envoi email: {e}")
        return jsonify({"error": "Erreur lors de l'envoi de l'email. Verifiez votre configuration SMTP."}), 500

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
    else:
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
    # Verifier encore une fois le code
    res = conn.execute('SELECT * FROM ResetCode WHERE Email = ? AND Code = ?', (email, code)).fetchone()
    
    if not res:
        conn.close()
        return jsonify({"error": "Action non autorisée"}), 403

    # Hasher le nouveau mot de passe
    hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
    
    # Mettre à jour
    conn.execute('UPDATE Utilisateur SET Mot_de_passe = ? WHERE Email = ?', (hashed_pw, email))
    conn.execute('DELETE FROM ResetCode WHERE Email = ?', (email,)) # Nettoyer
    conn.commit()
    conn.close()

    return jsonify({"message": "Mot de passe réinitialisé avec succès"}), 200



# 🚌 1. دالة جلب الكيران (GET)


@app.route('/get_buses', methods=['GET'])
def get_buses():
    try:
        conn = sqlite3.connect('smart_trans.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # نطلبوا كل الحقول من جدول Bus
        cursor.execute("SELECT * FROM Bus ORDER BY Code_bus DESC")
        rows = cursor.fetchall()
        conn.close()
        
        # نحولوا البيانات لـ قائمة فيها كل الحقول بما فيهم Code_chauffeur
        buses = [dict(ix) for ix in rows]
        return jsonify(buses)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
       
# ➕ 2. دالة إضافة كار جديدة (POST)
@app.route('/add_bus', methods=['POST'])
def add_bus():
    try:
        data = request.get_json()
        
        numero = data.get('Numero_bus')
        etat = data.get('Etat')
        # 🛑 التعديل هوني: لازم 'Code_chauffeur' موش 'ID_Chauffeur'
        id_chauffeur = data.get('Code_chauffeur') 

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO Bus (Numero_bus, Etat, Code_chauffeur) 
            VALUES (?, ?, ?)
        ''', (numero, etat, id_chauffeur))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Bus ajouté"}), 201
    except Exception as e:
        print(f"Erreur add_bus: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500
# 📝 3. دالة تعديل كار (PUT) - مصلحة 100%
@app.route('/update_bus/<int:id>', methods=['PUT'])
def update_bus(id):
    try:
        data = request.get_json()
        numero = data.get('Numero_bus')
        etat = data.get('Etat')
        id_chauffeur = data.get('Code_chauffeur')  # ✅ Corrigé: même clé que Flutter envoie

        conn = get_db_connection()
        
        # ✅ التغيير هنا: Code_chauffeur عوضاً عن ID_Chauffeur
        # ✅ والـ ID متاع الكار اسمو Code_bus
        conn.execute('''
            UPDATE Bus 
            SET Numero_bus = ?, Etat = ?, Code_chauffeur = ? 
            WHERE Code_bus = ?
        ''', (numero, etat, id_chauffeur, id))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Bus mis à jour"}), 200
    except Exception as e:
        print(f"Erreur update_bus: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 🗑️ 4. دالة حذف كار (DELETE) - مصلحة 100%
@app.route('/delete_bus/<int:id>', methods=['DELETE'])
def delete_bus(id):
    try:
        conn = get_db_connection()
        
        # 1. Nettoyage des incidents liés à ce bus
        conn.execute('DELETE FROM Incident WHERE Code_bus = ?', (id,))
        
        # 2. Mettre à NULL le Code_bus dans les lignes associées
        conn.execute('UPDATE Ligne SET Code_bus = NULL WHERE Code_bus = ?', (id,))
        
        # 3. Suppression du bus
        conn.execute('DELETE FROM Bus WHERE Code_bus = ?', (id,))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Bus et incidents associés supprimés"}), 200
    except Exception as e:
        print(f"Erreur delete_bus: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- 3. GESTION DES LIGNES ---
@app.route('/add_ligne', methods=['POST'])
def add_ligne():
    data = request.json
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ⚠️ ثبتي هوني: هل الأعمدة أساميهم Libelle و Description و Code_bus؟
        # حسب الـ Schema متاعك، هكا لازم يكون السطر:
        cursor.execute(
            "INSERT INTO Ligne (Libelle, Description, Code_bus) VALUES (?, ?, ?)",
            (data['libelle'], data['description'], data['code_bus'])
        )
        
        conn.commit()
        return jsonify({"message": "Ligne ajoutée avec succès"}), 201
    except Exception as e:
        print(f"Erreur Flask: {str(e)}") # هذي باش تطلعلك الغلطة في الـ Terminal
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/get_lignes', methods=['GET'])
def get_lignes():
    try:
        conn = get_db_connection()
        # نلوجوا في جدول Ligne اللي صنعناه حسب الدياغرام
        lignes = conn.execute('SELECT * FROM Ligne ORDER BY Code_Ligne DESC').fetchall()
        conn.close()
        
        # تحويل البيانات لـ List باش الـ Flutter يفهمها
        lignes_list = [dict(row) for row in lignes]
        print(f"DEBUG: Data sent to Flutter: {lignes_list}")
        
        return jsonify(lignes_list), 200
    except Exception as e:
        print(f"Erreur get_lignes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- حذف خط نقل (Delete Ligne) ---
@app.route('/delete_ligne/<int:id>', methods=['DELETE'])
def delete_ligne(id):
    try:
        conn = get_db_connection()
        
        # ❌ السطر القديم كان هكا (غالط):
        # conn.execute('DELETE FROM Ligne WHERE idLigne = ?', (id,))
        
        # ✅ السطر الجديد لازم يكون هكا (صحيح):
        conn.execute('DELETE FROM Ligne WHERE Code_Ligne = ?', (id,))
        
        conn.commit()
        conn.close()
        return jsonify({"message": "Ligne supprimée"}), 200
    except Exception as e:
        print(f"Erreur delete_ligne: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/update_ligne/<int:id>', methods=['PUT', 'POST'])
def update_ligne(id):
    try:
        data = request.get_json()
        # Support both casing for robustness
        libelle = data.get('libelle') or data.get('Libelle')
        description = data.get('description') or data.get('Description')
        code_bus = data.get('code_bus') or data.get('Code_bus')

        conn = get_db_connection()
        
        # We update all three fields: Libelle, Description, and Code_bus
        conn.execute('''
            UPDATE Ligne 
            SET Libelle = ?, Description = ?, Code_bus = ? 
            WHERE Code_Ligne = ?
        ''', (libelle, description, code_bus, id))
        
        conn.commit()
        conn.close()
        return jsonify({"message": "Ligne mise à jour"}), 200
    except Exception as e:
        print(f"Erreur update_ligne: {e}")
        return jsonify({"error": str(e)}), 500


# 1. جلب قائمة الكيران المتاحة
@app.route('/get_available_buses', methods=['GET'])
def get_available_buses():
    conn = sqlite3.connect('smart_trans.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT idBus, numeroBus FROM Bus") # تنجمي تزيديها WHERE idLigne IS NOT NULL
    buses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(buses)

# 2. ربط الشيفور بالكار
@app.route('/assign_bus_to_driver', methods=['POST'])
def assign_bus_to_driver():
    data = request.json
    id_chauffeur = data['idChauffeur']
    id_bus = data['idBus']
    
    conn = sqlite3.connect('smart_trans.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Chauffeur SET idBus = ? WHERE idChauffeur = ?", (id_bus, id_chauffeur))
    conn.commit()
    conn.close()
    return jsonify({"message": "Bus assigné avec succès"}), 200
# --- 4. GESTION DES CHAUFFEURS ---

@app.route('/get_chauffeurs', methods=['GET'])
def get_chauffeurs():
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        # 💡 زدنا Email هوني باش يقرأه Flutter
        query = """
        SELECT u.ID_utilisateur, u.Nom, u.Email, c.Code_chauffeur 
        FROM Chauffeur c
        JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
        ORDER BY c.Code_chauffeur DESC
        """
        cursor = conn.execute(query)
        rows = cursor.fetchall()
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
        # 🔐 HASH PASSWORD (هذا هو الإصلاح)
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        # 1. نضيفه في Utilisateur
        cursor = conn.execute(
            'INSERT INTO Utilisateur (Nom, Email, Mot_de_passe, Role) VALUES (?, ?, ?, ?)',
            (nom, email, hashed_pw, 'chauffeur')
        )

        user_id = cursor.lastrowid

        # 2. نضيفه في Chauffeur
        conn.execute(
            'INSERT INTO Chauffeur (ID_utilisateur) VALUES (?)',
            (user_id,)
        )

        conn.commit()
        return jsonify({"message": "Chauffeur ajouté avec succès"}), 201

    except Exception as e:
        print(f"Erreur: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

# --- حذف شيفور (Delete Chauffeur) ---
@app.route('/delete_chauffeur/<int:id>', methods=['DELETE']) # تأكدي من وجود <int:id>
def delete_chauffeur(id):
    try:
        conn = get_db_connection()
        # 1. نحيو الشوفير من جدول Chauffeur
        conn.execute('DELETE FROM Chauffeur WHERE ID_utilisateur = ?', (id,))
        
        # 2. نحيو المستخدم من جدول Utilisateur
        conn.execute('DELETE FROM Utilisateur WHERE ID_utilisateur = ?', (id,))
        
        conn.commit()
        conn.close()
        return jsonify({"message": "Chauffeur supprimé avec succès"}), 200
    except Exception as e:
        print(f"🚨 Erreur lors de la suppression: {e}")
        return jsonify({"error": str(e)}), 500
# --- تحديث بيانات شيفور (Update Chauffeur) ---
# --- تحديث بيانات شيفور (Update Chauffeur) ---
@app.route('/update_chauffeur/<int:id>', methods=['PUT'])
def update_chauffeur(id):
    try:
        data = request.get_json()
        nom = data.get('Nom')
        email = data.get('Email')
        password = data.get('Password') 
        
        conn = get_db_connection()
        
        # 🔐 HASH PASSWORD avant de sauvegarder
        if password:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        else:
            # Si aucun mot de passe fourni, garder l'ancien
            existing = conn.execute(
                'SELECT Mot_de_passe FROM Utilisateur WHERE ID_utilisateur = ?', (id,)
            ).fetchone()
            hashed_pw = existing['Mot_de_passe'] if existing else ''
        
        # نحدثوا البيانات في جدول Utilisateur
        conn.execute(
            'UPDATE Utilisateur SET Nom = ?, Email = ?, Mot_de_passe = ? WHERE ID_utilisateur = ?',
            (nom, email, hashed_pw, id)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Chauffeur mis à jour ✅"}), 200
    except Exception as e:
        print(f"🚨 Erreur: {e}")
        return jsonify({"error": str(e)}), 500

# --- 5. GÉRER PROFIL ---
@app.route('/get_profile/<email>', methods=['GET'])
def get_profile(email):
    conn = get_db_connection()
    user = conn.execute('SELECT Nom, Email, Photo FROM Utilisateur WHERE Email = ?', (email,)).fetchone()
    conn.close()
    if user: return jsonify({"Nom": user['Nom'], "Email": user['Email'], "Photo": user['Photo']}), 200
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
        
        # 1. Vérifier si l'email est déjà pris par un autre utilisateur
        if new_email:
            check_email = cursor.execute(
                "SELECT ID_utilisateur FROM Utilisateur WHERE Email = ? AND ID_utilisateur != ?", 
                (new_email, user_id)
            ).fetchone()
            if check_email:
                conn.close()
                return jsonify({"error": "Cet email est déjà utilisé par un autre compte"}), 400

        # 2. Préparer la requête de mise à jour
        query = "UPDATE Utilisateur SET Nom = ?, Email = ?, Photo = ?"
        params = [new_name, new_email, new_photo]

        # 3. Ajouter le mot de passe s'il est fourni
        if new_password and len(new_password) >= 6:
            hashed_pw = bcrypt.generate_password_hash(new_password).decode('utf-8')
            query += ", Mot_de_passe = ?"
            params.append(hashed_pw)
        
        query += " WHERE ID_utilisateur = ?"
        params.append(user_id)
        
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        
        return jsonify({"message": "Profil mis à jour avec succès ✅"}), 200
    except Exception as e:
        print(f"Erreur update_profile: {e}")
        return jsonify({"error": str(e)}), 500

# --- 6. GESTION PARCOURS ---
@app.route('/get_parcours/<int:code_ligne>', methods=['GET'])
def get_parcours_by_ligne(code_ligne):
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # هوني الفلترة: نجيبو كان السفرات اللي تابعة الخط هذا
        cursor.execute("SELECT * FROM Parcours WHERE Code_Ligne = ?", (code_ligne,))
        rows = cursor.fetchall()
        conn.close()
        
        return jsonify([dict(ix) for ix in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- إضافة رحلة جديدة (Add Parcours) ---
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
        return jsonify({"message": "Success"}), 201
    except Exception as e:
        print(f"🚨 Erreur SQL: {e}")
        return jsonify({"error": str(e)}), 500

# --- تحديث رحلة (Update Parcours) مصلح ---
@app.route('/update_parcours/<int:id>', methods=['PUT', 'POST', 'OPTIONS'])
def update_parcours(id):
    if request.method == 'OPTIONS': 
        return jsonify({"ok": True}), 200
    
    conn = get_db_connection()
    try:
        data = request.get_json(force=True)
        # Fix: Matching the actual table schema (Depart, Arrivee, Heure_depart, Heure_arrivee, Code_Ligne)
        conn.execute('''
            UPDATE Parcours 
            SET Depart = ?, Arrivee = ?, Heure_depart = ?, Heure_arrivee = ?, Code_Ligne = ? 
            WHERE ID_parcours = ?
        ''', (
            data.get('Depart'), 
            data.get('Arrivee'), 
            data.get('Heure_depart'), 
            data.get('Heure_arrivee'), 
            data.get('Code_Ligne'), 
            id
        ))
        
        conn.commit()
        return jsonify({"status": "success", "message": "Mise à jour réussie"}), 200
    except Exception as e:
        print(f"UPDATE ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/get_all_parcours', methods=['GET'])
def get_all_parcours():
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # We join with Ligne to get the label of the line
        query = """
            SELECT P.*, L.Libelle as Nom_Ligne
            FROM Parcours P
            JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            ORDER BY P.ID_parcours DESC
        """
        rows = cursor.execute(query).fetchall()
        conn.close()
        
        return jsonify([dict(ix) for ix in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- حذف رحلة (Delete Parcours) مصلح ---
@app.route('/delete_parcours/<int:id>', methods=['DELETE', 'OPTIONS'])
def delete_parcours(id):
    if request.method == 'OPTIONS': 
        return jsonify({"ok": True}), 200
        
    conn = get_db_connection()
    try:
        # 💡 بدلت Code_Parcours بـ ID_parcours
        cur = conn.execute('DELETE FROM Parcours WHERE ID_parcours = ?', (id,))
        conn.commit()
        
        if cur.rowcount > 0:
            return jsonify({"status": "success", "message": "Suppression réussie"}), 200
        else:
            return jsonify({"status": "error", "message": "Parcours non trouvé"}), 404
    except Exception as e:
        print(f"DELETE ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

# --- 7. INCIDENTS & AVIS (NLP Smart Section) ---
@app.route('/get_incidents', methods=['GET'])
def get_incidents():
    conn = get_db_connection()
    query = '''SELECT I.*, B.Numero_bus, U.Nom as NomChauffeur FROM Incident I
               JOIN Bus B ON I.Code_bus = B.Code_bus
               JOIN Chauffeur C ON B.Code_chauffeur = C.Code_chauffeur
               JOIN Utilisateur U ON C.ID_utilisateur = U.ID_utilisateur'''
    items = [dict(ix) for ix in conn.execute(query).fetchall()]
    conn.close()
    return jsonify(items)




@app.route('/add_avis', methods=['POST', 'OPTIONS'])
def add_avis():
    if request.method == 'OPTIONS':
        return jsonify({"ok": True}), 200

    data = request.get_json(force=True)
    comment = data.get('commentaire', '')
    note = data.get('note', 5)
    
    # Handle different key names between Dart and Python
    client_id = data.get('client_id') or data.get('code_client')
    parcours_id = data.get('parcours_id')
    id_historique = data.get('id_historique')
    
    # --- ANALYSE NLP AVANCÉE (GEMINI) ---
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
            # Nettoyage de la réponse pour extraire le JSON
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            ai_data = json.loads(res_text)
            
            sentiment_label = ai_data.get("sentiment", "Neutre")
            sentiment_score = float(ai_data.get("score", 0.0))
            category = ai_data.get("category", "Général")
            keywords = ai_data.get("keywords", "")
            is_risk = ai_data.get("risk", "Non")
            
            print(f"Gemini Analysis: {sentiment_label} | {category} | Risk: {is_risk}")
            
        except Exception as e:
            print(f"Erreur Gemini (Fallback TextBlob): {e}")
            # Fallback sur TextBlob si Gemini échoue
            if HAS_NLP:
                try:
                    translated_comment = GoogleTranslator(source='auto', target='en').translate(comment)
                    blob = TextBlob(translated_comment)
                except Exception:
                    blob = TextBlob(comment)
                sentiment_score = blob.sentiment.polarity
                
                # --- Modèle NLP Précis : Ajustement pondéré (Français & Derja Tunisienne) ---
                comment_lower = comment.lower()
                
                # Listes de mots avec poids
                strong_neg = ["catastrophe", "horrible", "honteux", "scandale", "khayeb", "masakh", "bhim", "msakh", "ykhawef", "danger", "vol", "arnaque", "catastrophique"]
                neg_words = ["n'aime pas", "n'aime plus", "déteste", "nul", "mauvais", "pire", "sale", "impoli", "retard", "lent", "problème", "panne", "froid", "chaud", "bruit", "saturé", "plein", "ma famech", "pas bien", "non", "désagréable"]
                
                strong_pos = ["parfait", "meilleur", "tayara", "magnifique", "extraordinaire", "top", "merveilleux", "incroyable"]
                pos_words = ["super", "excellent", "génial", "adore", "très bien", "bravo", "propre", "merci", "bahi", "behi", "cv", "bien", "bon", "rapide", "confortable", "gentil", "respectueux"]
                
                # Calcul de la pénalité / bonus
                bonus_malus = 0.0
                for w in strong_neg:
                    if w in comment_lower: bonus_malus -= 0.8
                for w in neg_words:
                    if w in comment_lower: bonus_malus -= 0.4
                for w in strong_pos:
                    if w in comment_lower: bonus_malus += 0.8
                for w in pos_words:
                    if w in comment_lower: bonus_malus += 0.4
                
                sentiment_score += bonus_malus
                sentiment_score = max(-1.0, min(1.0, sentiment_score)) # Normalisation

                if sentiment_score >= 0.15: sentiment_label = "Positif"
                elif sentiment_score <= -0.15: sentiment_label = "Négatif"
                else: sentiment_label = "Neutre"
                
                words = [word.lower() for word in comment.split() if len(word) > 3]
                keywords = ", ".join(list(set(words))[:5])

                # Catégorisation plus précise (Français & Derja)
                if any(w in comment_lower for w in ['chauffeur', 'conducteur', 'pilote', 'chafer', 'chaufeur']): category = "Chauffeur"
                elif any(w in comment_lower for w in ['confort', 'siege', 'clim', 'climatisation', 'chaud', 'froid', 'propre', 'sale', 'bruit', 'masakh', 'ndhif', 'korsi']): category = "Confort"
                elif any(w in comment_lower for w in ['bus', 'vehicule', 'panne', 'vieux', 'neuf', 'voiture', 'car', 'moteur', 'karoosa']): category = "Véhicule"
                elif any(w in comment_lower for w in ['retard', 'heure', 'temps', 'attente', 'horaire', 'ponctuel', 'regularite', 'trajet', 'ma famech', 'wqayet']): category = "Service"
    
    elif HAS_NLP and comment:
        # Code existant TextBlob si Gemini n'est pas configuré
        try:
            try:
                translated_comment = GoogleTranslator(source='auto', target='en').translate(comment)
                blob = TextBlob(translated_comment)
            except Exception:
                blob = TextBlob(comment)
            sentiment_score = blob.sentiment.polarity

            # --- Modèle NLP Précis : Ajustement pondéré (Français & Derja Tunisienne) ---
            comment_lower = comment.lower()
            
            # Listes de mots avec poids
            strong_neg = ["catastrophe", "horrible", "honteux", "scandale", "khayeb", "masakh", "bhim", "msakh", "ykhawef", "danger", "vol", "arnaque", "catastrophique"]
            neg_words = ["n'aime pas", "n'aime plus", "déteste", "nul", "mauvais", "pire", "sale", "impoli", "retard", "lent", "problème", "panne", "froid", "chaud", "bruit", "saturé", "plein", "ma famech", "pas bien", "non", "désagréable"]
            
            strong_pos = ["parfait", "meilleur", "tayara", "magnifique", "extraordinaire", "top", "merveilleux", "incroyable"]
            pos_words = ["super", "excellent", "génial", "adore", "très bien", "bravo", "propre", "merci", "bahi", "behi", "cv", "bien", "bon", "rapide", "confortable", "gentil", "respectueux"]
            
            # Calcul de la pénalité / bonus
            bonus_malus = 0.0
            for w in strong_neg:
                if w in comment_lower: bonus_malus -= 0.8
            for w in neg_words:
                if w in comment_lower: bonus_malus -= 0.4
            for w in strong_pos:
                if w in comment_lower: bonus_malus += 0.8
            for w in pos_words:
                if w in comment_lower: bonus_malus += 0.4
            
            sentiment_score += bonus_malus
            sentiment_score = max(-1.0, min(1.0, sentiment_score)) # Normalisation

            if sentiment_score >= 0.15: sentiment_label = "Positif"
            elif sentiment_score <= -0.15: sentiment_label = "Négatif"
            else: sentiment_label = "Neutre"
            
            words = [word.lower() for word in comment.split() if len(word) > 3]
            keywords = ", ".join(list(set(words))[:5])

            # Catégorisation plus précise (Français & Derja)
            if any(w in comment_lower for w in ['chauffeur', 'conducteur', 'pilote', 'chafer', 'chaufeur']): category = "Chauffeur"
            elif any(w in comment_lower for w in ['confort', 'siege', 'clim', 'climatisation', 'chaud', 'froid', 'propre', 'sale', 'bruit', 'masakh', 'ndhif', 'korsi']): category = "Confort"
            elif any(w in comment_lower for w in ['bus', 'vehicule', 'panne', 'vieux', 'neuf', 'voiture', 'car', 'moteur', 'karoosa']): category = "Véhicule"
            elif any(w in comment_lower for w in ['retard', 'heure', 'temps', 'attente', 'horaire', 'ponctuel', 'regularite', 'trajet', 'ma famech', 'wqayet']): category = "Service"
        except Exception as e:
            print(f"Erreur NLP: {e}")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 0. RESOLUTION DES INFOS MANQUANTES (Pour garantir que ID_parcours n'est pas NULL)
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

        # Résolution du bus si toujours NULL : Priorité au chauffeur, puis à la ligne
        if not code_bus and code_chauffeur:
            res_bus = cursor.execute("SELECT Code_bus FROM Bus WHERE Code_chauffeur = ?", (code_chauffeur,)).fetchone()
            if res_bus: code_bus = res_bus['Code_bus']
            
        if not code_bus and code_ligne:
            res_bus = cursor.execute("SELECT Code_bus FROM Ligne WHERE Code_Ligne = ?", (code_ligne,)).fetchone()
            if res_bus: code_bus = res_bus['Code_bus']

        # 1. Insertion de l'avis avec les scores IA
        cursor.execute("""
            INSERT INTO Avis 
            (Code_client, ID_historique, ID_parcours, Note, Commentaire, Sentiment_score, Sentiment_label, Keywords, Category, Date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            id_historique,
            parcours_id,
            note,
            comment,
            sentiment_score,
            sentiment_label,
            keywords,
            category,
            data.get('date', datetime.now().strftime("%Y-%m-%d"))
        ))
        
        # 2. MISE À JOUR AUTOMATIQUE DE LA PERFORMANCE DU CHAUFFEUR

        if code_chauffeur:
            # Nouveau calcul du score global du chauffeur : (Moyenne Notes + Moyenne Sentiment*0.5)
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

            # ⭐ MISE À JOUR DU SCORE DE VOYAGE (Par trajet) ⭐
            if id_historique:
                cursor.execute("""
                    UPDATE Historique 
                    SET Performance_IA = (
                        SELECT (AVG(Note) * 20) -- Convertir note 5 en score sur 100
                        FROM Avis WHERE ID_historique = ?
                    )
                    WHERE ID_historique = ?
                """, (id_historique, id_historique))

        # ⭐ DÉTECTION AUTOMATIQUE D'INCIDENT (SÉCURITÉ) ⭐
        if is_risk == "Oui":
            cursor.execute("""
                INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus)
                VALUES (?, ?, ?, ?, ?)
            """, (f"[IA ALERT] {comment}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code_chauffeur, code_ligne, code_bus))
            print(f"Incident de securite detecte automatiquement et enregistre !")

        conn.commit()
        conn.close()
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


# 1. سكور الشوفير (موجود في جدول Chauffeur)
@app.route('/get_driver_reviews/<int:user_id>', methods=['GET'])
def get_driver_reviews(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Trouver le Code_chauffeur à partir de l'ID_utilisateur
        res = cursor.execute("SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)).fetchone()
        if not res:
            conn.close()
            return jsonify([]), 200
            
        code_chauffeur = res['Code_chauffeur']
        
        # 2. Récupérer les avis
        query = """
            SELECT 
                A.Commentaire as commentaire, 
                A.Note as note, 
                A.Sentiment_label as sentiment, 
                A.Category as category, 
                A.Date as date
            FROM Avis A
            LEFT JOIN Historique H ON A.ID_historique = H.ID_historique
            LEFT JOIN Parcours P ON A.ID_parcours = P.ID_parcours
            LEFT JOIN Ligne L ON P.Code_Ligne = L.Code_Ligne
            LEFT JOIN Bus B ON L.Code_bus = B.Code_bus
            WHERE H.Code_chauffeur = ? OR B.Code_chauffeur = ?
            ORDER BY A.Date DESC
        """
        cursor.execute(query, (code_chauffeur, code_chauffeur))
        rows = cursor.fetchall()
        
        reviews = [dict(row) for row in rows]
        
        conn.close()
        return jsonify(reviews), 200
    except Exception as e:
        print(f"Error get_driver_reviews: {e}")
        return jsonify([]), 200 

# 2. الخط المخصص للشوفير

       



# 📊 Stats pour le Chauffeur (Score & Avis)
@app.route('/get_driver_stats/<int:user_id>', methods=['GET'])
def get_driver_stats(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Trouver le code_chauffeur à partir de l'ID_utilisateur
        res = cursor.execute("SELECT Code_chauffeur, Performance_score FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)).fetchone()
        if not res:
            return jsonify({"error": "Chauffeur non trouvé"}), 404
            
        code_chauffeur = res['Code_chauffeur']
        perf_score = res['Performance_score']
        
        # Récupérer les derniers avis avec sentiment (via Historique ou Parcours)
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
        
        # Stats par catégorie pour ce chauffeur
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
        
        # Count incidents for this driver
        incident_count = cursor.execute("SELECT COUNT(*) FROM Incident WHERE Code_chauffeur = ?", (code_chauffeur,)).fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "performance_score": round(perf_score, 2),
            "incident_count": incident_count,
            "recent_reviews": [dict(row) for row in avis],
            "category_distribution": {row['Category']: row['count'] for row in cat_stats}
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/get_counts', methods=['GET'])
def get_counts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # نحسبوا من الجداول الجديدة حسب الـ MLD متاعك
        lignes = cursor.execute('SELECT COUNT(*) FROM Ligne').fetchone()[0]
        chauffeurs = cursor.execute('SELECT COUNT(*) FROM Chauffeur').fetchone()[0]
        bus = cursor.execute('SELECT COUNT(*) FROM Bus').fetchone()[0]
        incidents = cursor.execute('SELECT COUNT(*) FROM Incident').fetchone()[0]
        
        conn.close()
        return jsonify({
            "lignes": lignes,
            "chauffeurs": chauffeurs,
            "bus": bus,
            "incidents": incidents
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_performance_v2', methods=['GET'])
def get_performance_v2():
    conn = get_db_connection()
    try:
        # استعملنا COUNT(*) باش نحسبو عدد الأسطر من غير ما نحتاجو لـ ID معين
        query = '''
            SELECT 
                U.Nom as Nom_Chauffeur,
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
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
@app.route('/finish_parcours/<int:id_p>', methods=['PUT'])
def finish_parcours(id_p):
    conn = get_db_connection()
    try:
        import datetime
        heure_arrivee = datetime.datetime.now().strftime("%H:%M")
        
        # Consistent column names: ID_parcours
        conn.execute('''
            UPDATE Parcours 
            SET Heure_arrivee = ?, statut = 'Terminé' 
            WHERE ID_parcours = ?
        ''', (heure_arrivee, id_p))
        
        conn.commit()
        return jsonify({"status": "success", "heure_arrivee": heure_arrivee}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/add_incident', methods=['POST'])
def add_incident():
    try:
        data = request.json
        description = data.get('description')
        
        # 1. هوني نحددو الـ ID متاع الشيفور والخط (للتجربة حطيهم 1 و 402)
        # ملاحظة: في النسخة الجاية نجيبوهم مالـ Login
        id_chauffeur = 1  
        id_ligne = 1 # أو 402 حسب الـ ID اللي عندك في جدول Ligne
        
        date_incident = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect('smart_trans.db')
        cursor = conn.cursor()
        
        # 2. التعديل المهم: نزيدو Code_chauffeur و Code_Ligne و Code_bus في الـ INSERT
        # نلوجو على الكار المربوطة بالشيفور
        res_bus = cursor.execute("SELECT Code_bus FROM Bus WHERE Code_chauffeur = ?", (id_chauffeur,)).fetchone()
        code_bus = res_bus['Code_bus'] if res_bus else None

        cursor.execute("""
            INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus) 
            VALUES (?, ?, ?, ?, ?)
        """, (description, date_incident, id_chauffeur, id_ligne, code_bus))
        
        conn.commit()
        conn.close()
        
        print(f"Incident enregistre : Chauffeur {id_chauffeur} sur Ligne {id_ligne}")
        return jsonify({"message": "Incident ajouté avec succès"}), 201
    except Exception as e:
        print(f"Erreur SQL: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/manage_parcours', methods=['POST'])
def manage_parcours():
    try:
        data = request.json
        action = data.get('action') # 'start' أو 'end'
        p_depart = data.get('Depart', '---')
        p_arrivee = data.get('Arrivee', '---')
        p_heure = data.get('Heure_depart', datetime.now().strftime("%H:%M"))
        p_ligne = data.get('Code_Ligne', 1) 

        conn = sqlite3.connect('smart_trans.db')
        cursor = conn.cursor()

        if action == 'start':
            # تسجيل بداية الرحلة
            cursor.execute("""
                INSERT INTO Parcours (Depart, Arrivee, Heure_depart, Heure_arrivee, Code_Ligne) 
                VALUES (?, ?, ?, '--:--', ?)
            """, (p_depart, p_arrivee, p_heure, p_ligne))
            conn.commit()
            print(f"Parcours Demarre: {p_depart} -> {p_arrivee} à {p_heure}")
            msg = "Parcours démarré 🚌"

        elif action == 'end':
            # 1. نجيبو وقت الوصول الحالي
            now_end = datetime.now()
            heure_arrivee_str = now_end.strftime("%H:%M")
            
            # 2. نلوجو على آخر رحلة لهذا الخط مافيهاش وقت وصول
            cursor.execute("""
                UPDATE Parcours 
                SET Heure_arrivee = ? 
                WHERE Code_Ligne = ? AND (Heure_arrivee = '--:--' OR Heure_arrivee IS NULL)
            """, (heure_arrivee_str, p_ligne))
            conn.commit()
            msg = f"Parcours terminé ✅ à {heure_arrivee_str}"

        conn.close()
        return jsonify({"status": "success", "message": msg}), 200

    except Exception as e:
        print(f"Erreur General: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_my_reviews/<int:id_chauffeur>', methods=['GET'])
def get_my_reviews(id_chauffeur):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # On utilise ID_parcours pour lier les avis au chauffeur (ou via Code_chauffeur direct)
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
        print(f"Erreur SQL get_my_reviews: {e}")
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
        # 1. نربطو الشوفير بالكار في جدول Bus
        cursor.execute("UPDATE Bus SET Code_chauffeur = ? WHERE Code_bus = ?", 
                       (code_chauffeur, code_bus))
        
        # 2. نربطو الكار بالخط في جدول Ligne
        cursor.execute("UPDATE Ligne SET Code_bus = ? WHERE Code_Ligne = ?", 
                       (code_bus, code_ligne))
        
        conn.commit()
        return jsonify({"message": "Affectation réussie ! Line, Bus et Chauffeur sont liés."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()




@app.route('/get_my_assignment/<int:user_id>', methods=['GET'])
def get_my_assignment(user_id):
    try:
        conn = sqlite3.connect('smart_trans.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")

        # Query avec LEFT JOIN pour voir les lignes même sans parcours
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
        print(f"Erreur SQL get_my_assignment: {e}")
        return jsonify([]), 500
        



@app.route('/get_all_incidents', methods=['GET'])
def get_all_incidents():
    try:
        conn = get_db_connection()
        # نربطوا الجداول باش نجيبوا رقم الكار واسم الخط بطريقة ذكية (Robust Fallback)
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

@app.route('/delete_incident/<int:id>', methods=['DELETE'])
def delete_incident(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM Incident WHERE ID_incident = ?', (id,))
        conn.commit()
        conn.close()
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
        return jsonify({"message": "Success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 📱 Endpoint pour le Dashboard Client (Lignes + Historique des trajets)
@app.route('/get_client_trips', methods=['GET'])
def get_client_trips():
    try:
        conn = get_db_connection()
        # 1. On récupère les lignes
        lignes = conn.execute("SELECT * FROM Ligne").fetchall()
        
        result = []
        for l in lignes:
            # 2. Pour chaque ligne, on cherche les trajets RÉELS (Historique) qui ont eu lieu
            query_hist = """
                SELECT h.ID_historique, h.Date, h.Depart, h.Arrivee, u.Nom as Nom_Chauffeur
                FROM Historique h
                JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
                JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
                JOIN Parcours p ON h.ID_parcours = p.ID_parcours
                WHERE p.Code_Ligne = ?
                ORDER BY h.Date DESC
            """
            # DEBUG: Si ça ne marche pas, essayez d'enlever le join Chauffeur pour voir si c'est lui qui bloque
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

@app.route('/get_all_lignes', methods=['GET'])
def get_all_lignes():
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # Query تجيب الخط، الكار، واسم الشوفير اللي مربوط بالكار
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

@app.route('/get_avis_by_client/<int:client_id>', methods=['GET'])
def get_avis_by_client(client_id):
    try:
        conn = get_db_connection()

        avis = conn.execute("""
            SELECT 
                a.ID_avis,
                a.Commentaire,
                a.Note,
                a.Date,
                h.Depart,
                h.Arrivee
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

        conn.execute("""
            UPDATE Avis 
            SET Commentaire = ?, Note = ?
            WHERE ID_avis = ?
        """, (commentaire, note, id))

        conn.commit()
        conn.close()

        return jsonify({"message": "updated"}), 200

    except Exception as e:
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





# 1. دالة جلب التقييمات الخاص بالشوفور


# 2. دالة تسجيل الحوادث
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
        
        # 1. Trouver le Code_chauffeur à partir de l'ID_utilisateur
        res_chauffeur = cursor.execute("SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)).fetchone()
        if not res_chauffeur:
            conn.close()
            return jsonify({"error": "Chauffeur non trouvé pour cet utilisateur"}), 404
            
        code_chauffeur = res_chauffeur['Code_chauffeur']
        
        # 2. Trouver le Code_bus et Code_Ligne associés à ce chauffeur
        # On cherche d'abord via le Bus (Liaison directe Chauffeur -> Bus)
        res_info = cursor.execute("""
            SELECT B.Code_bus, L.Code_Ligne 
            FROM Bus B 
            LEFT JOIN Ligne L ON B.Code_bus = L.Code_bus 
            WHERE B.Code_chauffeur = ?
            LIMIT 1
        """, (code_chauffeur,)).fetchone()
        
        code_bus = res_info['Code_bus'] if res_info else None
        code_ligne = res_info['Code_Ligne'] if res_info else data.get('line_id', 1)

        # 3. Insertion de l'incident avec toutes les infos
        cursor.execute("""
            INSERT INTO Incident (Description, Date, Code_chauffeur, Code_Ligne, Code_bus) 
            VALUES (?, ?, ?, ?, ?)
        """, (description, timestamp, code_chauffeur, code_ligne, code_bus))
        
        conn.commit()
        conn.close()
        print(f"Incident déclaré: Bus {code_bus}, Chauffeur {code_chauffeur}")
        return jsonify({"message": "Incident signalé avec succès"}), 201
    except Exception as e:
        print(f"Erreur declare_incident: {e}")
        return jsonify({"error": str(e)}), 500

# 3. دالة تسجيل بداية ونهاية السفرة (Historique)
@app.route('/log_historique', methods=['POST'])
def log_historique():
    try:
        data = request.get_json()
        action = data['action']  # 'Début' ou 'Fin'
        user_id = data['driver_id']
        parcours_id = data['parcours_id']
        now = data['timestamp']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Find the actual Code_chauffeur from user_id
        res_chauffeur = cursor.execute("SELECT Code_chauffeur FROM Chauffeur WHERE ID_utilisateur = ?", (user_id,)).fetchone()
        if not res_chauffeur:
            conn.close()
            return jsonify({"error": "Chauffeur non trouvé"}), 404
            
        code_chauffeur = res_chauffeur['Code_chauffeur']

        if action == "Début":
            # On enregistre le départ avec la direction actuelle (envoyée par le frontend)
            cursor.execute("""
                INSERT INTO Historique (Date, Heure_fin, Statut, Depart, Arrivee, Performance_IA, ID_parcours, Code_chauffeur) 
                VALUES (?, NULL, 'En cours', ?, ?, NULL, ?, ?)
            """, (now, data.get('depart'), data.get('arrivee'), parcours_id, code_chauffeur))
            message = "Voyage démarré"
        
        elif action == "Fin":
            # On met à jour le dernier trajet 'En cours' pour ce chauffeur et ce parcours
            cursor.execute("""
                UPDATE Historique 
                SET Heure_fin = ?, Statut = 'Terminé', Performance_IA = 100.0 
                WHERE Code_chauffeur = ? AND ID_parcours = ? AND Statut = 'En cours'
            """, (now, code_chauffeur, parcours_id))
            
            if cursor.rowcount == 0:
                # Fallback: si pas trouvé avec 'En cours', on cherche le dernier sans Heure_fin
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




# ─────────────────────────────────────────────────────────────────
# 🔄 RE-CATÉGORISATION NLP de tous les avis existants
# ─────────────────────────────────────────────────────────────────
DRIVER_KEYWORDS = [
    'chauffeur', 'conducteur', 'pilote', 'chafer', 'chaufeur',
    'impoli', 'poli', 'grossier', 'aimable', 'sympa', 'agressif',
    'comportement', 'conduite', 'attitude', 'professionnel',
    'vitesse', 'rapide', 'lent', 'freinage', 'accelere',
    'respectueux', 'irrespectueux', 'souriant', 'desagreable',
    'competent', 'incompetent', 'courtois', 'imprudent', 'prudent'
]
COMFORT_KEYWORDS = ['confort', 'siege', 'clim', 'climatisation', 'chaud', 'froid', 'propre', 'sale', 'bruit']
VEHICLE_KEYWORDS = ['bus', 'vehicule', 'panne', 'vieux', 'neuf', 'voiture', 'car', 'moteur']
SERVICE_KEYWORDS = ['retard', 'heure', 'temps', 'attente', 'horaire', 'ponctuel', 'regularite', 'trajet']

def categorize_comment(comment):
    c = comment.lower()
    if any(w in c for w in DRIVER_KEYWORDS):
        return 'Chauffeur'
    elif any(w in c for w in COMFORT_KEYWORDS):
        return 'Confort'
    elif any(w in c for w in VEHICLE_KEYWORDS):
        return 'Véhicule'
    elif any(w in c for w in SERVICE_KEYWORDS):
        return 'Service'
    return 'Général'

@app.route('/recategorize_avis', methods=['POST'])
def recategorize_avis():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        rows = cursor.execute("SELECT ID_avis, Commentaire FROM Avis WHERE Commentaire IS NOT NULL AND Commentaire != ''").fetchall()
        updated = 0
        for row in rows:
            new_cat = categorize_comment(row['Commentaire'])
            cursor.execute("UPDATE Avis SET Category = ? WHERE ID_avis = ?", (new_cat, row['ID_avis']))
            updated += 1
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "updated": updated}), 200
    except Exception as e:
        print(f"Erreur recategorize: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# 📊 Rapport NLP spécifique aux AVIS CHAUFFEUR
# ─────────────────────────────────────────────────────────────────
@app.route('/get_driver_nlp_report', methods=['GET'])
def get_driver_nlp_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total avis chauffeur
        total = cursor.execute("SELECT COUNT(*) FROM Avis WHERE Category = 'Chauffeur'").fetchone()[0]

        # Distribution sentiments (chauffeur seulement)
        sentiments = cursor.execute("""
            SELECT Sentiment_label, COUNT(*) as count
            FROM Avis WHERE Category = 'Chauffeur'
            GROUP BY Sentiment_label
        """).fetchall()
        sentiment_dist = {r['Sentiment_label']: r['count'] for r in sentiments}

        # Score moyen
        avg_score = cursor.execute(
            "SELECT AVG(Sentiment_score) FROM Avis WHERE Category = 'Chauffeur'"
        ).fetchone()[0] or 0

        # Note moyenne
        avg_note = cursor.execute(
            "SELECT AVG(Note) FROM Avis WHERE Category = 'Chauffeur'"
        ).fetchone()[0] or 0

        # Mots-clés des avis chauffeur
        kw_rows = cursor.execute("SELECT Keywords FROM Avis WHERE Category = 'Chauffeur' AND Keywords != ''").fetchall()
        kw_counts = {}
        for r in kw_rows:
            if r['Keywords']:
                for kw in r['Keywords'].split(', '):
                    kw = kw.strip()
                    if kw:
                        kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_keywords = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Liste des avis chauffeur avec nom client
        avis_rows = cursor.execute("""
            SELECT a.*,
                   COALESCE(u.Nom, 'Client #' || CAST(a.Code_client AS TEXT)) as Nom_Client
            FROM Avis a
            LEFT JOIN Client c ON a.Code_client = c.Code_client
            LEFT JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            WHERE a.Category = 'Chauffeur'
            ORDER BY a.Date DESC
        """).fetchall()

        # Top chauffeurs mentionnés
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


# 📊 Endpoint pour le Rapport d'Analyse IA complet (Admin)
@app.route('/get_nlp_report', methods=['GET'])
def get_nlp_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Statistiques globales de sentiment
        total_avis = cursor.execute("SELECT COUNT(*) FROM Avis").fetchone()[0]
        sentiments = cursor.execute("SELECT Sentiment_label, COUNT(*) as count FROM Avis GROUP BY Sentiment_label").fetchall()
        sentiment_stats = {row['Sentiment_label']: row['count'] for row in sentiments}
        
        
        # 2. Moyenne des scores
        avg_score = cursor.execute("SELECT AVG(Sentiment_score) FROM Avis").fetchone()[0] or 0
        
        # 3. Mots-clés les plus fréquents
        all_keywords = cursor.execute("SELECT Keywords FROM Avis WHERE Keywords != ''").fetchall()
        keyword_counts = {}
        for row in all_keywords:
            if row['Keywords']:
                for kw in row['Keywords'].split(", "):
                    kw = kw.strip()
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # 4. Top 3 Chauffeurs (selon sentiment IA)
        top_drivers = cursor.execute("""
            SELECT u.Nom, AVG(a.Sentiment_score) as avg_sentiment, COUNT(a.ID_avis) as nb_avis
            FROM Avis a
            JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Chauffeur c ON h.Code_chauffeur = c.Code_chauffeur
            JOIN Utilisateur u ON c.ID_utilisateur = u.ID_utilisateur
            GROUP BY c.Code_chauffeur
            ORDER BY avg_sentiment DESC LIMIT 3
        """).fetchall()

        # 5. Satisfaction par Parcours (Routes) - NEW (Improved with fallback)
        parcours_stats = cursor.execute("""
            SELECT p.ID_parcours, p.Depart, p.Arrivee, AVG(a.Sentiment_score) as avg_sentiment, COUNT(a.ID_avis) as nb_avis
            FROM Avis a
            LEFT JOIN Historique h ON a.ID_historique = h.ID_historique
            JOIN Parcours p ON (a.ID_parcours = p.ID_parcours OR (a.ID_parcours IS NULL AND h.ID_parcours = p.ID_parcours))
            GROUP BY p.ID_parcours
            ORDER BY avg_sentiment DESC
        """).fetchall()
        
        # 6. Statistiques de Sécurité (NEW - Gemini)
        safety_alerts = cursor.execute("SELECT COUNT(*) FROM Incident WHERE Description LIKE '[IA ALERT]%'").fetchone()[0]
        
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
        print(f"Erreur get_parcours_reviews: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_all_historique', methods=['GET'])
def get_all_historique():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # We join Historique with Utilisateur (via Chauffeur) to get the driver's name
        # and Parcours/Ligne for more details if necessary.
        query = """
            SELECT 
                h.ID_historique, 
                h.Date, 
                h.Heure_fin, 
                h.Statut, 
                h.Depart, 
                h.Arrivee, 
                h.Performance_IA,
                u.Nom as Nom_Chauffeur,
                l.Libelle as Nom_Ligne
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



@app.route('/test', methods=['GET', 'POST'])
def test():
    print("سيرفر وصله طلب!")
    return jsonify({"message": "السيرفر يخدم!"})


if __name__ == '__main__':
    try:
        init_all_tables()
        print("Database connection successful and tables checked!")
    except Exception as e:
        print(f"Error during database init: {e}")
    
    # التغيير هنا:
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
