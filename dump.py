import sqlite3

con = sqlite3.connect('smart_trans.db')
with open('smart_trans.sql', 'w', encoding='utf-8') as f:
    for line in con.iterdump():
        f.write('%s\n' % line)
print("🎯 المِلَفّ تخلّق بنجاح يا شذا!")