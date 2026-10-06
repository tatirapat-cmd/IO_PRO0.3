from flask import Flask, render_template, request, jsonify, Response
import json
import inventory_logic as logic

app = Flask(__name__)

default_db = logic.load_data()

def get_current_db():
    try:
        data = request.get_json(silent=True) or {}
        client_db = data.get('client_db')
        if client_db and isinstance(client_db, dict):
            for k in ["users", "products", "stock_cards", "audit_logs", "purchase_orders", "supplier_pos"]:
                if k not in client_db or not isinstance(client_db[k], list):
                    client_db[k] = []
            return client_db
    except Exception:
        pass
    return default_db

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        username = data.get('username', '')
        password = data.get('password', '')
        role = data.get('role', 'customer')
        name = data.get('name', '')

        success, msg = logic.register_user(db_data["users"], username, password, role, name)
        if success:
            logic.add_audit_log(db_data["audit_logs"], username, role, "REGISTER", f"สมัครสมาชิกใหม่ ({name})")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในระบบ: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        username = data.get('username', '')
        password = data.get('password', '')

        success, msg, user_info = logic.authenticate_user(db_data["users"], username, password)
        if success:
            logic.add_audit_log(db_data["audit_logs"], user_info["username"], user_info["role"], "LOGIN", "เข้าสู่ระบบสำเร็จ")
            return jsonify({'success': True, 'user': user_info, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการเข้าสู่ระบบ: {str(e)}"}), 500

@app.route('/api/summary', methods=['POST'])
def get_summary():
    try:
        db_data = get_current_db()
        summary = logic.calculate_inventory_summary(db_data["products"])
        return jsonify({'success': True, 'data': summary})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการโหลดข้อมูลสรุป: {str(e)}"}), 500

@app.route('/api/products', methods=['POST'])
def get_products():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        search = data.get('search', '')
        category = data.get('category', '')
        sort_by = data.get('sort_by', 'sku')
        page = data.get('page', 1)
        per_page = data.get('per_page', 20)

        items, pagination = logic.filter_and_paginate(
            db_data["products"], search_term=search, category=category, sort_by=sort_by, page=page, per_page=per_page
        )
        return jsonify({'success': True, 'products': items, 'pagination': pagination})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการเรียกดูรายการสินค้า: {str(e)}"}), 500

@app.route('/api/products/add', methods=['POST'])
def add_product():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'คุณไม่มีสิทธิ์ดำเนินการเพิ่มสินค้า'}), 403

        val_success, val_msg, val_data = logic.validate_product_input(
            sku=data.get('sku'), name=data.get('name'), cost_str=data.get('cost_price'),
            price_str=data.get('selling_price'), qty_str=data.get('quantity'), min_stock_str=data.get('min_stock', 5)
        )

        if not val_success:
            return jsonify({'success': False, 'message': val_msg}), 400

        val_data.update({
            "company": data.get('company', '-'),
            "category": data.get('category', 'ทั่วไป'),
            "unit": data.get('unit', 'ชิ้น'),
            "supplier": data.get('supplier', data.get('company', '-')),
            "warehouse": data.get('warehouse', 'คลังหลัก')
        })

        add_success, add_msg = logic.add_product(db_data["products"], val_data)
        if add_success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'ADD_PRODUCT', f"เพิ่มสินค้า: {val_data['sku']} - {val_data['name']}")
            return jsonify({'success': True, 'message': add_msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': add_msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการเพิ่มสินค้า: {str(e)}"}), 500

@app.route('/api/products/update', methods=['POST'])
def update_product():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        sku = data.get('sku')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'คุณไม่มีสิทธิ์ดำเนินการแก้ไขสินค้า'}), 403

        up_success, up_msg = logic.update_product(db_data["products"], sku, data)
        if up_success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'EDIT_PRODUCT', f"แก้ไขสินค้า SKU: {sku}")
            return jsonify({'success': True, 'message': up_msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': up_msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการแก้ไขสินค้า: {str(e)}"}), 500

@app.route('/api/products/restock', methods=['POST'])
def restock_product():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        sku = data.get('sku')
        action_type = data.get('action_type', 'in')
        quantity = data.get('quantity', 0)
        reason = data.get('reason', 'เติม/ปรับสต๊อกสินค้า')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'คุณไม่มีสิทธิ์ดำเนินการปรับสต๊อกสินค้า'}), 403

        success, msg, movement = logic.process_stock_movement(
            db_data["products"], db_data["stock_cards"], sku=sku, action_type=action_type,
            qty_change=quantity, reason=reason, operator=username
        )

        if success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'STOCK_MOVEMENT', f"{action_type.upper()} {sku} จำนวน {quantity} ชิ้น ({reason})")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการปรับสต๊อก: {str(e)}"}), 500

@app.route('/api/products/delete', methods=['POST'])
def delete_product():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        sku = data.get('sku')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'คุณไม่มีสิทธิ์ดำเนินการลบสินค้า'}), 403

        del_success, del_msg = logic.delete_product(db_data["products"], sku)
        if del_success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'DELETE_PRODUCT', f"ลบสินค้า SKU: {sku}")
            return jsonify({'success': True, 'message': del_msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': del_msg}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการลบสินค้า: {str(e)}"}), 500

@app.route('/api/products/delete-multiple', methods=['POST'])
def delete_multiple_products_route():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        skus = data.get('skus', [])

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'คุณไม่มีสิทธิ์ดำเนินการลบสินค้า'}), 403

        if not skus or not isinstance(skus, list):
            return jsonify({'success': False, 'message': 'กรุณาระบุรายการ SKU ที่ต้องการลบ'}), 400

        success, msg, count = logic.delete_multiple_products(db_data["products"], skus)
        if success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'DELETE_PRODUCTS', f"ลบสินค้าหลายรายการจำนวน {count} SKU: {', '.join(skus)}")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการลบสินค้า: {str(e)}"}), 500

@app.route('/api/orders', methods=['POST'])
def get_orders():
    try:
        db_data = get_current_db()
        return jsonify({'success': True, 'orders': db_data["purchase_orders"]})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการดึงรายการคำสั่งซื้อ: {str(e)}"}), 500

@app.route('/api/orders/create', methods=['POST'])
def create_order():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        sku = data.get('sku')
        qty = data.get('quantity', 1)
        customer = data.get('customer_name', 'Guest')

        success, msg, new_order = logic.create_customer_order(
            db_data["purchase_orders"], db_data["products"], sku=sku, qty=qty, cust_name=customer
        )

        if success:
            logic.add_audit_log(db_data["audit_logs"], customer, 'customer', 'CREATE_ORDER', f"สร้างคำสั่งซื้อ {new_order['order_id']} ({sku} x {qty})")
            return jsonify({'success': True, 'message': msg, 'order': new_order, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการสร้างคำสั่งซื้อ: {str(e)}"}), 500

@app.route('/api/orders/approve', methods=['POST'])
def approve_order():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        order_id = data.get('order_id')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'คุณไม่มีสิทธิ์อนุมัติคำสั่งซื้อ'}), 403

        order = next((o for o in db_data["purchase_orders"] if o.get('order_id') == order_id), None)
        if not order:
            return jsonify({'success': False, 'message': 'ไม่พบคำสั่งซื้อที่ระบุ'}), 404

        success, msg, movement = logic.approve_customer_order(
            db_data["products"], db_data["stock_cards"], order=order, operator=username
        )

        if success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'APPROVE_ORDER', f"อนุมัติคำสั่งซื้อ {order_id}")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการอนุมัติคำสั่งซื้อ: {str(e)}"}), 500

@app.route('/api/po', methods=['POST'])
def get_supplier_pos():
    try:
        db_data = get_current_db()
        return jsonify({'success': True, 'supplier_pos': db_data["supplier_pos"]})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการดึงรายการ PO: {str(e)}"}), 500

@app.route('/api/po/create', methods=['POST'])
def create_supplier_po_route():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        supplier = data.get('supplier')
        sku = data.get('sku')
        qty = data.get('quantity')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'ไม่มีสิทธิ์ออกใบสั่งซื้อ PO'}), 403

        success, msg, po = logic.create_supplier_po(
            db_data["supplier_pos"], db_data["products"], supplier, sku, qty
        )

        if success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'CREATE_PO', f"ออกใบสั่งซื้อ PO: {po['po_id']} ({sku} x {qty})")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการออกใบสั่งซื้อ PO: {str(e)}"}), 500

@app.route('/api/po/receive', methods=['POST'])
def receive_supplier_po_route():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        role = data.get('current_role')
        username = data.get('current_user')
        po_id = data.get('po_id')

        if role not in ['admin', 'staff']:
            return jsonify({'success': False, 'message': 'ไม่มีสิทธิ์รับสินค้าตาม PO'}), 403

        success, msg = logic.receive_supplier_po(
            db_data["supplier_pos"], db_data["products"], db_data["stock_cards"], po_id=po_id, operator=username
        )

        if success:
            logic.add_audit_log(db_data["audit_logs"], username, role, 'RECEIVE_PO', f"รับสินค้าตามใบสั่งซื้อ PO: {po_id}")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการรับสินค้า PO: {str(e)}"}), 500

@app.route('/api/stock-cards', methods=['POST'])
def get_stock_cards():
    try:
        db_data = get_current_db()
        data = request.get_json() or {}
        sku = data.get('sku', '')
        cards = db_data["stock_cards"]
        if sku:
            cards = [c for c in cards if sku.upper() in c.get('sku', '').upper()]
        return jsonify({'success': True, 'stock_cards': cards})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการดึงประวัติสต๊อก: {str(e)}"}), 500

@app.route('/api/logs', methods=['POST'])
def get_logs():
    try:
        db_data = get_current_db()
        return jsonify({'success': True, 'audit_logs': db_data["audit_logs"]})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการดึง Audit Logs: {str(e)}"}), 500

@app.route('/api/export/excel', methods=['POST'])
def export_excel():
    try:
        db_data = get_current_db()
        excel_stream = logic.export_products_to_excel(db_data["products"])
        return Response(
            excel_stream.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": "attachment; filename=inventory_report.xlsx"}
        )
    except Exception as e:
        return jsonify({'success': False, 'message': f"ส่งออกไฟล์ไม่สำเร็จ: {str(e)}"}), 500

@app.route('/api/import/excel', methods=['POST'])
def import_excel():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'กรุณาแนบไฟล์ Excel'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'ไม่ได้เลือกไฟล์'}), 400

        client_db_raw = request.form.get('client_db')
        if client_db_raw:
            try:
                db_data = json.loads(client_db_raw)
            except Exception:
                db_data = get_current_db()
        else:
            db_data = get_current_db()

        success, msg, count = logic.import_products_from_excel(file, db_data["products"])
        if success:
            logic.add_audit_log(db_data["audit_logs"], "admin", "admin", "IMPORT_EXCEL", f"นำเข้าสินค้า {count} รายการจากไฟล์ Excel")
            return jsonify({'success': True, 'message': msg, 'db_data': db_data})
        return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการนำเข้าไฟล์: {str(e)}"}), 500

@app.route('/api/categories', methods=['POST'])
def get_categories():
    try:
        db_data = get_current_db()
        categories = sorted(list(set(p.get("category") for p in db_data["products"] if p.get("category"))))
        return jsonify({'success': True, 'categories': categories})
    except Exception as e:
        return jsonify({'success': False, 'message': f"เกิดข้อผิดพลาดในการดึงหมวดหมู่: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
