from flask import Flask, render_template_string, request, jsonify
import pymysql
import win32print
import win32ui
import win32con

app = Flask(__name__)

# زانیارییەکانی بەستنەوە بە داتابەیسی Railway
DB_CONFIG = {
    'host': 'sakura.proxy.rlwy.net',
    'port': 31707,
    'user': 'root',
    'password': 'HITVDFaMFehpQFmWrZlnaTKtavNtBZyw',
    'database': 'nrx',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

# فەنکشنی چاپکردنی وەسڵی چێشتخانە لەسەر قەبارەی 8cm (80mm) بە فۆنتی کوردی
def print_receipt(table_num, items_list):
    printers = ["XP-80C", "XP-80C (copy 1)"]

    for printer_name in printers:
        try:
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                hdc = win32ui.CreateDC()
                hdc.CreatePrinterDC(printer_name)
                hdc.StartDoc("Kitchen Receipt")
                hdc.StartPage()

                # فۆنتەکان بۆ چاپی کوردی
                font_title = win32ui.CreateFont({
                    "name": "Noto Kufi Arabic",
                    "height": 38,
                    "weight": 800,
                    "charset": win32con.ARABIC_CHARSET
                })
                
                font_header = win32ui.CreateFont({
                    "name": "Noto Kufi Arabic",
                    "height": 30,
                    "weight": 700,
                    "charset": win32con.ARABIC_CHARSET
                })
                
                font_items = win32ui.CreateFont({
                    "name": "Noto Kufi Arabic",
                    "height": 28,
                    "weight": 700,
                    "charset": win32con.ARABIC_CHARSET
                })

                y = 10
                
                # سەردێڕ
                hdc.SelectObject(font_title)
                hdc.TextOut(130, y, "شاهور ڕێستۆرانت")
                y += 45

                hdc.SelectObject(font_header)
                hdc.TextOut(140, y, "وەسڵی چێشتخانە")
                y += 40

                # ژمارەی مێز
                hdc.TextOut(160, y, f"مێزی: {table_num}")
                y += 45

                hdc.SelectObject(font_items)
                hdc.TextOut(10, y, "------------------------------------------")
                y += 35
                
                hdc.TextOut(380, y, "خواردن")
                hdc.TextOut(50, y, "بڕ")
                y += 35
                hdc.TextOut(10, y, "------------------------------------------")
                y += 35

                # لیستی خواردنەکان
                for item in items_list:
                    name = str(item.get('name', ''))
                    qty = str(item.get('qty', 1))
                    
                    hdc.TextOut(180, y, name)
                    hdc.TextOut(60, y, f"x{qty}")
                    y += 40

                hdc.TextOut(10, y, "------------------------------------------")
                y += 80

                hdc.EndPage()
                hdc.EndDoc()
            finally:
                win32print.ClosePrinter(hprinter)
        except Exception as err:
            print(f"هەڵە لە چاپی پرێنتەری {printer_name}: {err}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ckb" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>مێنیوی شاهور</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Noto Kufi Arabic', sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: #0b0f19; color: #f8fafc; padding-bottom: 110px; }
        
        .app-header {
            background: linear-gradient(180deg, #161f32 0%, #0b0f19 100%);
            padding: 16px 16px 8px;
            text-align: center;
            border-bottom: 1px solid rgba(245, 158, 11, 0.2);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .restaurant-name { color: #f59e0b; font-size: 20px; font-weight: 800; }
        .tagline { color: #94a3b8; font-size: 11px; margin-top: 2px; }

        .table-bar {
            background: #1e293b;
            margin: 12px 16px;
            padding: 10px 14px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border: 1px solid #334155;
        }
        .table-bar label { font-weight: 700; font-size: 13px; color: #f8fafc; }
        .table-select {
            background: #0f172a;
            color: #f59e0b;
            border: 1.5px solid #f59e0b;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            outline: none;
        }

        .categories-scroll {
            display: flex;
            overflow-x: auto;
            gap: 8px;
            padding: 4px 16px 12px;
            scrollbar-width: none;
        }
        .categories-scroll::-webkit-scrollbar { display: none; }
        .cat-chip {
            background: #1e293b;
            color: #94a3b8;
            padding: 7px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
            text-decoration: none;
            border: 1px solid #334155;
        }
        .cat-chip.active { background: #f59e0b; color: #0b0f19; font-weight: 800; border-color: #f59e0b; }

        .menu-container { padding: 0 16px; }
        .category-block { margin-bottom: 18px; }
        .category-title { color: #f59e0b; font-size: 15px; font-weight: 700; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
        .category-title::after { content: ''; flex: 1; height: 1px; background: #334155; }
        
        .food-card {
            background: #151d30;
            border: 1px solid #243048;
            border-radius: 14px;
            padding: 10px;
            margin-bottom: 10px;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .food-img { width: 68px; height: 68px; border-radius: 10px; object-fit: cover; background: #0b0f19; border: 1px solid #334155; flex-shrink: 0; }
        .food-details { flex: 1; min-width: 0; }
        .food-name { font-size: 14px; font-weight: 700; color: #ffffff; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .food-price { font-size: 13px; font-weight: 700; color: #10b981; }
        
        .counter-group { display: flex; align-items: center; background: #0b0f19; border-radius: 8px; border: 1px solid #334155; padding: 2px; gap: 3px; }
        .btn-count { width: 30px; height: 30px; border-radius: 6px; border: none; background: #1e293b; color: #ffffff; font-size: 15px; font-weight: 700; cursor: pointer; }
        .btn-count.plus { background: #f59e0b; color: #0b0f19; }
        .qty-val { width: 26px; text-align: center; font-size: 14px; font-weight: 700; color: #ffffff; background: transparent; border: none; outline: none; }

        .bottom-cart-bar {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            background: rgba(15, 23, 42, 0.96);
            backdrop-filter: blur(10px);
            border-top: 1px solid #334155;
            padding: 10px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            z-index: 200;
        }
        .cart-info-btn {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #1e293b;
            padding: 8px 14px;
            border-radius: 10px;
            border: 1px solid #334155;
            cursor: pointer;
        }
        .cart-badge { background: #f59e0b; color: #0b0f19; font-size: 11px; font-weight: 800; padding: 2px 7px; border-radius: 10px; }
        .cart-total-txt { font-size: 14px; font-weight: 800; color: #10b981; }
        .btn-send-main {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: #0b0f19;
            border: none;
            padding: 10px 20px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 800;
            cursor: pointer;
        }

        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 300;
            display: none;
            align-items: flex-end;
        }
        .modal-sheet {
            background: #151d30;
            width: 100%;
            max-height: 80vh;
            border-radius: 20px 20px 0 0;
            padding: 18px 16px;
            display: flex;
            flex-direction: column;
            border-top: 1px solid #334155;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; border-bottom: 1px solid #334155; padding-bottom: 8px; }
        .modal-title { font-size: 16px; font-weight: 800; color: #f59e0b; }
        .close-btn { background: none; border: none; color: #ef4444; font-size: 18px; font-weight: 800; cursor: pointer; }
        .cart-items-list { overflow-y: auto; flex: 1; max-height: 50vh; margin-bottom: 14px; }
        .cart-item-row { display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 10px; border-radius: 8px; margin-bottom: 8px; }
        .del-item-btn { color: #ef4444; background: none; border: none; font-size: 16px; cursor: pointer; margin-right: 8px; }
    </style>
</head>
<body>

    <header class="app-header">
        <div class="restaurant-name">✨ شاهور ڕێستۆرانت</div>
        <div class="tagline">سیستەمی داواکاری مۆبایل</div>
    </header>

    <div class="table-bar">
        <label>📍 ژمارەی مێزەکەت:</label>
        <select name="table_number" id="tableSelect" class="table-select" onchange="fetchTableOrders(this.value)" required>
            {% for num in range(1, 31) %}
                <option value="{{ num }}">مێزی {{ num }}</option>
            {% endfor %}
        </select>
    </div>

    <div class="categories-scroll">
        <a href="javascript:void(0)" class="cat-chip active" onclick="filterCat('all', this)">هەموو</a>
        {% for cat in categories.keys() %}
            <a href="javascript:void(0)" class="cat-chip" onclick="filterCat('cat-{{ loop.index }}', this)">{{ cat }}</a>
        {% endfor %}
    </div>

    <div class="menu-container">
        {% for cat, items in categories.items() %}
        <div class="category-block" id="cat-{{ loop.index }}">
            <div class="category-title">{{ cat }}</div>
            {% for item in items %}
            <div class="food-card">
                <img src="{{ item.image_path if item.image_path and item.image_path.startswith('http') else 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=200' }}" class="food-img" onerror="this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=200'">
                
                <div class="food-details">
                    <div class="food-name">{{ item.food_name }}</div>
                    <div class="food-price">{{ "{:,.0f}".format(item.price) }} دینار</div>
                </div>

                <div class="counter-group">
                    <button type="button" class="btn-count" onclick="updateQty('{{ item.food_name }}', -1, {{ item.price }}, '{{ item.category }}')">-</button>
                    <input type="text" id="qty_{{ item.food_name }}" value="0" class="qty-val" readonly>
                    <button type="button" class="btn-count plus" onclick="updateQty('{{ item.food_name }}', 1, {{ item.price }}, '{{ item.category }}')">+</button>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>

    <div class="bottom-cart-bar">
        <div class="cart-info-btn" onclick="openCartModal()">
            <span style="font-size: 18px;">🛒</span>
            <span class="cart-badge" id="cartCount">0</span>
            <span class="cart-total-txt" id="cartTotalTxt">0 دینار</span>
        </div>
        <button type="button" class="btn-send-main" onclick="submitFinalOrder()">ناردنی داواکاری ➔</button>
    </div>

    <div class="modal-overlay" id="cartModal" onclick="closeCartModal(event)">
        <div class="modal-sheet" onclick="event.stopPropagation()">
            <div class="modal-header">
                <span class="modal-title">🛒 خواردنەکانی ناو سەبەتە</span>
                <button type="button" class="close-btn" onclick="toggleCartModal(false)">✕</button>
            </div>
            <div class="cart-items-list" id="cartItemsList"></div>
            <button type="button" class="btn-send-main" style="width: 100%; padding: 12px;" onclick="submitFinalOrder()">تۆمارکردن لە سیستەم</button>
        </div>
    </div>

    <script>
        let cart = {}; 

        function resetInputs() {
            document.querySelectorAll('.qty-val').forEach(el => el.value = 0);
        }

        function updateQty(foodName, change, price, cat) {
            if (!cart[foodName]) {
                cart[foodName] = { qty: 0, price: price, cat: cat || '' };
            }
            
            cart[foodName].qty += change;
            if (cart[foodName].qty <= 0) {
                delete cart[foodName];
            }

            const input = document.getElementById('qty_' + foodName);
            if (input) input.value = cart[foodName] ? cart[foodName].qty : 0;

            renderCartSummary();
        }

        function removeFoodEntirely(foodName) {
            delete cart[foodName];
            const input = document.getElementById('qty_' + foodName);
            if (input) input.value = 0;
            renderCartSummary();
            renderCartModalList();
        }

        function renderCartSummary() {
            let total = 0;
            let count = 0;
            for (let name in cart) {
                total += (cart[name].qty * cart[name].price);
                count += cart[name].qty;
            }
            document.getElementById('cartTotalTxt').innerText = total.toLocaleString() + ' دینار';
            document.getElementById('cartCount').innerText = count;
        }

        function openCartModal() {
            renderCartModalList();
            toggleCartModal(true);
        }

        function toggleCartModal(show) {
            document.getElementById('cartModal').style.display = show ? 'flex' : 'none';
        }

        function closeCartModal(e) {
            if (e.target.id === 'cartModal') toggleCartModal(false);
        }

        function renderCartModalList() {
            const list = document.getElementById('cartItemsList');
            list.innerHTML = '';
            
            if (Object.keys(cart).length === 0) {
                list.innerHTML = '<div style="text-align:center; color:#94a3b8; padding:20px;">هیچ خواردنێک لە سەبەتەکەدا نییە!</div>';
                return;
            }

            for (let name in cart) {
                const item = cart[name];
                const row = document.createElement('div');
                row.className = 'cart-item-row';
                row.innerHTML = `
                    <div style="display:flex; align-items:center;">
                        <button type="button" class="del-item-btn" onclick="removeFoodEntirely('${name}')">🗑</button>
                        <div>
                            <div style="font-weight:700; font-size:13px; color:#fff;">${name}</div>
                            <div style="color:#10b981; font-size:11px;">${(item.qty * item.price).toLocaleString()} دینار</div>
                        </div>
                    </div>
                    <div class="counter-group">
                        <button type="button" class="btn-count" onclick="updateQty('${name}', -1, ${item.price}, '${item.cat}'); renderCartModalList();">-</button>
                        <span style="padding:0 8px; font-weight:700;">${item.qty}</span>
                        <button type="button" class="btn-count plus" onclick="updateQty('${name}', 1, ${item.price}, '${item.cat}'); renderCartModalList();">+</button>
                    </div>
                `;
                list.appendChild(row);
            }
        }

        function filterCat(catId, btn) {
            document.querySelectorAll('.cat-chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');

            const blocks = document.querySelectorAll('.category-block');
            if (catId === 'all') {
                blocks.forEach(b => b.style.display = 'block');
            } else {
                blocks.forEach(b => b.style.display = (b.id === catId) ? 'block' : 'none');
            }
        }

        function fetchTableOrders(tableNum) {
            fetch('/get_table_orders/' + tableNum)
                .then(res => res.json())
                .then(data => {
                    cart = {};
                    resetInputs();
                    
                    if (data.length > 0) {
                        data.forEach(item => {
                            cart[item.food_name] = {
                                qty: parseInt(item.quantity),
                                price: parseFloat(item.price),
                                cat: item.category || ''
                            };
                            const input = document.getElementById('qty_' + item.food_name);
                            if (input) input.value = item.quantity;
                        });
                    }
                    renderCartSummary();
                });
        }

        function submitFinalOrder() {
            const tableNum = document.getElementById('tableSelect').value;
            fetch('/save_cart_order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ table_number: tableNum, cart: cart })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    toggleCartModal(false);
                    alert('داواکارییەکە تۆمارکرا و ڕاستەوخۆ نێردرا بۆ پرێنتەرەکانی چێشتخانە!');
                    fetchTableOrders(tableNum);
                } else {
                    alert('هەڵە: ' + data.message);
                }
            });
        }

        window.onload = function() {
            fetchTableOrders(document.getElementById('tableSelect').value);
        };
    </script>
</body>
</html>
"""

@app.route('/')
def menu():
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("SELECT food_name, price, category, image_path FROM nse WHERE food_name IS NOT NULL AND food_name != ''")
            foods = cursor.fetchall()
        conn.close()

        categories = {}
        for food in foods:
            cat = food['category'] if food['category'] else 'گشتی'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(food)

        return render_template_string(HTML_TEMPLATE, categories=categories)
    except Exception as e:
        return f"<h3 style='color:red; text-align:center;'>کێشە لە پەیوەندی داتابەیس: {str(e)}</h3>"

@app.route('/get_table_orders/<table_num>')
def get_table_orders(table_num):
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT food_name, price, category, SUM(quantity) as quantity, SUM(quantity * price) as total 
                FROM froshtn 
                WHERE table_cabin = %s 
                GROUP BY food_name, price, category
            """, (str(table_num),))
            orders = cursor.fetchall()
        conn.close()
        return jsonify(orders)
    except:
        return jsonify([])

@app.route('/save_cart_order', methods=['POST'])
def save_cart_order():
    data = request.get_json()
    table_num = data.get('table_number')
    cart_data = data.get('cart', {})

    conn = get_db()
    try:
        printed_items = []
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM froshtn WHERE table_cabin = %s", (str(table_num),))

            for food_name, item in cart_data.items():
                qty = int(item['qty'])
                price = float(item['price'])
                cat = item.get('cat', '')
                if qty > 0:
                    cursor.execute("""
                        INSERT INTO froshtn (table_cabin, food_name, quantity, price, category, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (str(table_num), food_name, qty, price, cat))
                    
                    printed_items.append({'name': food_name, 'qty': qty})

            conn.commit()
        conn.close()

        # فەرمانی چاپی ئۆتۆماتیکی بۆ پرێنتەرەکان
        if printed_items:
            print_receipt(table_num, printed_items)

        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.close()
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)