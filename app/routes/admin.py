from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
from database import get_db_connection
import random  # For genetic algorithm and simulation
import math  # For any mathematical operations
from datetime import datetime
from collections import defaultdict
import random, copy, json
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin_homepage')
def admin_homepage():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Query notifications count from shift_swap_requests table for NurseAccepted status
    cursor.execute("SELECT COUNT(*) FROM shift_swap_requests WHERE status = 'NurseAccepted'")
    notification_count = cursor.fetchone()[0]
    session['notification_count'] = notification_count

    cursor.close()
    conn.close()

    return render_template(
        'admin/admin_homepage.html',
        hospital_name=session.get('hospital_name'),
        admin_name=session.get('user_name'),
        notification_count=notification_count  # pass it here
    )


@admin_bp.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor()
    admin_id = session['user_id']

    # Fetch total number of nurses
    cur.execute("SELECT COUNT(*) FROM nurses WHERE admin_id = %s", (admin_id,))
    total_nurses = cur.fetchone()[0]

    # Fetch active and inactive nurses
    cur.execute("SELECT COUNT(*) FROM nurses WHERE admin_id = %s AND status = 'Active'", (admin_id,))
    active_nurses = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM nurses WHERE admin_id = %s AND status = 'Inactive'", (admin_id,))
    inactive_nurses = cur.fetchone()[0]

    # Fetch category breakdown
    cur.execute("SELECT department, COUNT(*) FROM nurses WHERE admin_id = %s GROUP BY department", (admin_id,))
    category_breakdown = cur.fetchall()  # This will be a list of tuples (e.g., [("Senior", 12), ("Junior", 10)])

    cur.execute("SELECT category, COUNT(*) FROM nurses WHERE admin_id = %s GROUP BY category", (admin_id,))
    category = cur.fetchall()  # This will be a list of tuples (e.g., [("Senior", 12), ("Junior", 10)])

    cur.close()
    conn.close()

    # Pass the data to the template
    return render_template(
        'admin/admin_dashboard.html',
        total_nurses=total_nurses,
        active_nurses=active_nurses,
         category_breakdown=category_breakdown,
         category=category,
        inactive_nurses=inactive_nurses,
       
    )

# Manage Nurses Route
@admin_bp.route('/manage_nurses', methods=['GET', 'POST'])
def manage_nurses():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor()
    admin_id = session['user_id']

    # Fetch nurses for the current admin
    query = "SELECT * FROM nurses WHERE admin_id = %s"
    cur.execute(query, (admin_id,))
    nurses = cur.fetchall()

    # Handle search/filter
    if request.method == 'POST':
        search_query = request.form.get('search')
        filter_category = request.form.get('filter_category')

        if search_query or filter_category:
            sql = "SELECT * FROM nurses WHERE admin_id = %s"
            params = [admin_id]

            if search_query:
                sql += " AND (LOWER(name) LIKE LOWER(%s) OR LOWER(email) LIKE LOWER(%s))"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            if filter_category:
                sql += " AND category = %s"
                params.append(filter_category)

            cur.execute(sql, tuple(params))
            nurses = cur.fetchall()

    # Render content-only template for AJAX
    return render_template('admin/manage_nurse.html', nurses=nurses)

# Add Nurse Route
@admin_bp.route('/add_nurse', methods=['POST'])
def add_nurse():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    data = request.form
    conn = get_db_connection()
    cur = conn.cursor()
    admin_id = session['user_id']

    try:
        cur.execute("""
            INSERT INTO nurses (admin_id, name, email, phone, shift_preference, sleep_hours, category, department, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            admin_id, data['name'], data['email'], data['phone'], 
            data['shift_preference'], data['sleep_hours'], data['category'],
            data['department'], 'Active'  # Assuming 'Active' by default
        ))
        conn.commit()
        flash('Nurse added successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error adding nurse: {e}', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin.manage_nurses'))

@admin_bp.route('/edit_nurse/<int:nurse_id>', methods=['GET', 'POST'])
def edit_nurse(nurse_id):
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch the current nurse's information
    cur.execute("SELECT * FROM nurses WHERE nurse_id = %s", (nurse_id,))
    nurse = cur.fetchone()

    if nurse is None:
        flash('Nurse not found!', 'error')
        return redirect(url_for('admin.manage_nurses'))

    # If it's a POST request, handle the form submission
    if request.method == 'POST':
        try:
            # Get updated data from the form
            name = request.form['name']
            email = request.form['email']
            phone = request.form['phone']
            shift_preference = request.form['shift_preference']
            sleep_hours = request.form['sleep_hours']
            category = request.form['category']
            department = request.form['department']
            status = request.form['status']

            # Update the nurse's record in the database
            cur.execute("""
                UPDATE nurses
                SET name = %s, email = %s, phone = %s, shift_preference = %s, 
                    sleep_hours = %s, category = %s, department = %s, status = %s
                WHERE nurse_id = %s
            """, (
                name, email, phone, shift_preference, sleep_hours, category, department, status, nurse_id
            ))
            conn.commit()

            flash('Nurse updated successfully!', 'success')
            return redirect(url_for('admin.manage_nurses'))
        except Exception as e:
            flash(f"Error updating nurse: {e}", 'error')
            conn.rollback()

    # Render the edit form with the nurse's data
    return render_template('admin/edit_nurse.html', nurse=nurse)


# Delete Nurse Route
@admin_bp.route('/delete_nurse/<int:nurse_id>', methods=['POST'])
def delete_nurse(nurse_id):
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM nurses WHERE nurse_id = %s AND admin_id = %s", (nurse_id, session['user_id']))
        conn.commit()
        flash('Nurse deleted successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting nurse: {e}', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin.manage_nurses'))

@admin_bp.route('/edit_admin_info', methods=['GET', 'POST'])
def edit_admin_info():
    # Check if the user is logged in
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    admin_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'GET':
        # Fetch the current admin's information
        cur.execute("""
            SELECT name, email, hospital_name, hospital_address
            FROM hospital_admin
            WHERE admin_id = %s
        """, (admin_id,))
        admin_info = cur.fetchone()

        if admin_info:
            # Return the current info to the template
            return render_template('admin/edit_admin_info.html', admin_info=admin_info)
        else:
            flash('Admin information not found.', 'error')
            return redirect(url_for('admin.admin_homepage'))

    elif request.method == 'POST':
        # Get the edited data from the form
        name = request.form.get('name')
        email = request.form.get('email')
        hospital_name = request.form.get('hospital_name')
        hospital_address = request.form.get('hospital_address')

        try:
            # Update the admin's information
            cur.execute("""
                UPDATE hospital_admin
                SET name = %s, email = %s, hospital_name = %s, hospital_address = %s, updated_at = CURRENT_TIMESTAMP
                WHERE admin_id = %s
            """, (name, email, hospital_name, hospital_address, admin_id))
            conn.commit()

            flash('Your information has been updated successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error updating information: {e}', 'error')
        finally:
            cur.close()
            conn.close()

        return redirect(url_for('admin.edit_admin_info'))


def get_shift_end_time(shift_start):
    """
    Function to map shift start time to a human-readable combined shift time.
    """
    shift_end_map = {
        '08:00:00': '8 AM to 4 PM',   # 8 AM to 4 PM shift
        '16:00:00': '4 PM to 12 AM',  # 4 PM to 12 AM shift
        '00:00:00': '12 AM to 8 AM'   # 12 AM to 8 AM shift
    }
    return shift_end_map.get(shift_start, 'Unknown')



from flask import render_template, request, session, flash, redirect, url_for
import json, random, copy

@admin_bp.route('/generate_schedule', methods=['GET', 'POST'])
def generate_schedule():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))

    # Get the current admin's id from the session.
    admin_id = session.get('user_id')
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Query all active nurses including shift preferences.
    cur.execute(
        "SELECT nurse_id, name, shift_preference FROM nurses WHERE status = 'Active' AND admin_id = %s",
        (admin_id,)
    )
    nurses = cur.fetchall()
    if not nurses:
        flash("No nurses found.", "error")
        cur.close()
        conn.close()
        return render_template('admin/generate_schedule.html', schedule=None)

    nurse_ids = [n[0] for n in nurses]
    nurse_map = {n[0]: n[1] for n in nurses}
    nurse_preferences = {n[0]: n[2] for n in nurses}  # nurse_id -> shift_preference (Morning, Afternoon, Evening)

    # Define days and original shift labels (for frontend rendering).
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    shift_labels = ['8 AM to 4 PM', '4 PM to 12 AM', '12 AM to 8 AM']
    total_shifts = len(days) * len(shift_labels)  # 21 shifts per week

    # Read user-specified nurses per shift from the form.
    nurses_per_shift_input = request.form.get('nurses_per_shift')
    try:
        user_nurses_per_shift = int(nurses_per_shift_input)
    except (TypeError, ValueError):
        user_nurses_per_shift = 0

    # Build shift_info list as a list of tuples: (day, shift, target number of nurses).
    shift_info = []
    if user_nurses_per_shift > 0:
        for day in days:
            for shift in shift_labels:
                shift_info.append((day, shift, user_nurses_per_shift))
        total_slots = user_nurses_per_shift * total_shifts
        if total_slots < len(nurse_ids):
            flash("Warning: The total number of scheduled slots is less than the number of nurses. Some nurses may not be assigned.", "warning")
    else:
        base = len(nurse_ids) // total_shifts
        remainder = len(nurse_ids) % total_shifts
        shift_index = 0
        for day in days:
            for shift in shift_labels:
                target = base + 1 if shift_index < remainder else base
                shift_info.append((day, shift, target))
                shift_index += 1

    # GA Parameters.
    POP_SIZE = 50
    GENERATIONS = 100
    MUTATION_RATE = 0.1

    # Define disallowed consecutive shifts.
    disallowed = {
        '8 AM to 4 PM': '4 PM to 12 AM',
        '4 PM to 12 AM': '12 AM to 8 AM',
        '12 AM to 8 AM': '8 AM to 4 PM'
    }

    # Mapping of nurse preference to corresponding shift label.
    pref_mapping = {
        "Morning": "8 AM to 4 PM",
        "Afternoon": "12 AM to 8 AM",
        "Evening": "4 PM to 12 AM"
    }

    def repair_candidate(candidate):
        """
        Ensures that every nurse in nurse_ids appears at least once in the candidate,
        if the total number of scheduled slots is sufficient.
        """
        # Flatten the candidate schedule.
        assigned = set()
        for gene in candidate:
            assigned.update(gene)
        missing = [nid for nid in nurse_ids if nid not in assigned]
        total_slots = sum(len(gene) for gene in candidate)
        if total_slots < len(nurse_ids):
            # Not enough slots to cover all nurses.
            return candidate
        # For each missing nurse, replace a random nurse in a random shift.
        for nid in missing:
            gene_index = random.randrange(len(candidate))
            gene = candidate[gene_index]
            pos = random.randrange(len(gene))
            gene[pos] = nid
        return candidate

    def create_candidate():
        """Create a random candidate schedule biased to use nurses with matching preferences.
           Then repair it to ensure all nurses are involved (if possible)."""
        candidate = []
        for (day, shift, target) in shift_info:
            # Determine expected nurse preference for this shift.
            expected_pref = None
            for pref, mapped_shift in pref_mapping.items():
                if mapped_shift == shift:
                    expected_pref = pref
                    break
            # Get list of nurses whose preference matches the expected one.
            preferred_nurses = [nid for nid in nurse_ids if nurse_preferences.get(nid) == expected_pref]
            if len(preferred_nurses) >= target:
                candidate.append(random.sample(preferred_nurses, target))
            else:
                # If not enough preferred nurses, fill the remainder with others.
                chosen = preferred_nurses.copy()
                remaining = target - len(chosen)
                others = [nid for nid in nurse_ids if nid not in chosen]
                if remaining > len(others):
                    candidate.append(chosen + random.sample(nurse_ids, remaining))
                else:
                    candidate.append(chosen + random.sample(others, remaining))
        # Repair the candidate so that every nurse is included, if possible.
        candidate = repair_candidate(candidate)
        return candidate

    def initial_population():
        """Generate the initial population."""
        return [create_candidate() for _ in range(POP_SIZE)]

    def fitness(candidate):
        """Compute a fitness penalty for a candidate schedule."""
        penalty = 0
        # Build assignments per nurse: nurse_id -> list of (shift index, day, shift_label).
        assignments = {nid: [] for nid in nurse_ids}
        for idx, gene in enumerate(candidate):
            day, shift, target = shift_info[idx]
            # Penalty for duplicate nurse assignments within the same shift.
            if len(gene) != len(set(gene)):
                penalty += 5 * (len(gene) - len(set(gene)))
            for nurse_id in gene:
                assignments[nurse_id].append((idx, day, shift))
        # Check for disallowed consecutive shifts.
        for nid, asg in assignments.items():
            asg.sort(key=lambda x: x[0])
            for i in range(len(asg) - 1):
                _, _, shift_current = asg[i]
                _, _, shift_next = asg[i + 1]
                if disallowed.get(shift_current) == shift_next:
                    penalty += 10
        # Penalize assignments that do not match nurse shift preferences.
        for nurse_id, asg in assignments.items():
            pref = nurse_preferences.get(nurse_id)
            if pref and pref in pref_mapping:
                expected_shift = pref_mapping[pref]
                for _, day, shift in asg:
                    if shift != expected_shift:
                        penalty += 20  # Penalty for mismatch.
        # Reduced penalty for uneven distribution – we care less about perfect balance.
        total_assignments = sum(len(gene) for gene in candidate)
        ideal = total_assignments / len(nurse_ids)
        for nid in nurse_ids:
            count = len(assignments[nid])
            penalty += 0.2 * abs(count - ideal)  # Much lower weight.

        # Very heavy penalty for any nurse that is not scheduled.
        for nid in nurse_ids:
            if len(assignments[nid]) == 0:
                penalty += 200

        return penalty

    def selection(population):
        """Tournament selection: choose the best out of 3 randomly picked candidates."""
        selected = []
        for _ in range(len(population)):
            contenders = random.sample(population, 3)
            best = min(contenders, key=fitness)
            selected.append(best)
        return selected

    def crossover(parent1, parent2):
        """Uniform crossover: for each shift gene, randomly choose from one parent."""
        child = []
        for gene1, gene2 in zip(parent1, parent2):
            child.append(copy.deepcopy(gene1) if random.random() < 0.5 else copy.deepcopy(gene2))
        return child

    def mutate(candidate):
        """Mutate a candidate by randomly replacing one nurse in a gene, with a bias toward matching preference."""
        for i in range(len(candidate)):
            if random.random() < MUTATION_RATE:
                gene = candidate[i]
                pos = random.randrange(len(gene))
                day, shift, target = shift_info[i]
                # Determine expected nurse preference for this shift.
                expected_pref = None
                for pref, mapped_shift in pref_mapping.items():
                    if mapped_shift == shift:
                        expected_pref = pref
                        break
                preferred_nurses = [nid for nid in nurse_ids if nurse_preferences.get(nid) == expected_pref]
                # Try to pick a nurse from the preferred list first.
                possible = [nid for nid in preferred_nurses if nid not in gene] or [nid for nid in nurse_ids if nid not in gene]
                if possible:
                    gene[pos] = random.choice(possible)
                else:
                    gene[pos] = random.choice(nurse_ids)
        return candidate

    def genetic_algorithm():
        """Run the GA to generate a candidate schedule."""
        population = initial_population()
        best_candidate = None
        best_fit = float('inf')
        for generation in range(GENERATIONS):
            population.sort(key=fitness)
            current_best = population[0]
            current_fit = fitness(current_best)
            if current_fit < best_fit:
                best_fit = current_fit
                best_candidate = current_best
            if best_fit == 0:
                break  # Ideal candidate found.
            selected = selection(population)
            next_population = []
            for i in range(0, len(selected), 2):
                if i + 1 < len(selected):
                    child1 = crossover(selected[i], selected[i + 1])
                    child2 = crossover(selected[i + 1], selected[i])
                    mutate(child1)
                    mutate(child2)
                    next_population.extend([child1, child2])
                else:
                    next_population.append(selected[i])
            population = next_population
        return best_candidate

    if request.method == 'POST':
        candidate = genetic_algorithm()

        # Delete previous schedules for the current admin.
        cur.execute(
            "DELETE FROM schedules WHERE status = 'Scheduled' AND admin_id = %s",
            (admin_id,)
        )
        conn.commit()

        # Insert the generated schedule into the database.
        # (Using the original shift labels so the frontend remains unchanged.)
        for idx, gene in enumerate(candidate):
            day, shift_label, target = shift_info[idx]
            shift_start = shift_label.split(' to ')[0]
            for nurse_id in gene:
                cur.execute(
                    """
                    INSERT INTO schedules (nurse_id, shift_day, shift_start, shift_end, status, admin_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (nurse_id, day, shift_start, shift_label, "Scheduled", admin_id)
                )
        conn.commit()
        flash("Schedule generated successfully!", "success")

    # Load any preexisting schedule data for the current admin.
    cur.execute(
        """
        SELECT s.schedule_id, n.name AS nurse_name, s.nurse_id, s.shift_day, s.shift_start, s.shift_end, s.status 
        FROM schedules s
        JOIN nurses n ON s.nurse_id = n.nurse_id
        WHERE s.status = 'Scheduled' AND s.admin_id = %s
        """,
        (admin_id,)
    )
    schedule_data = cur.fetchall()
    schedule = {day: [] for day in days}
    for entry in schedule_data:
        day = entry[3]
        schedule[day].append({
            "schedule_id": entry[0],  # Added schedule_id
            "shift_start": entry[4],
            "shift_end": entry[5],
            "nurse_name": entry[1]
        })

    # Retrieve the latest swap request for the current admin and determine swapped schedule IDs.
    swapped_schedule_ids = []
    cur.execute(
        """
        SELECT current_schedule_id, desired_schedule_id, requester_nurse_id, target_nurse_id
        FROM shift_swap_requests
        WHERE admin_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (admin_id,)
    )
    latest_swap = cur.fetchone()
    if latest_swap:
        current_schedule_id = latest_swap[0]
        desired_schedule_data = latest_swap[1]
        requester_nurse_id = latest_swap[2]
        target_nurse_id = latest_swap[3]
        desired_schedule_ids = json.loads(desired_schedule_data) if desired_schedule_data else []
        all_swap_ids = []
        if current_schedule_id:
            all_swap_ids.append(current_schedule_id)
        if desired_schedule_ids:
            all_swap_ids.extend(desired_schedule_ids)
        if all_swap_ids:
            placeholders = ','.join(['%s'] * len(all_swap_ids))
            query = f"""
                SELECT schedule_id
                FROM schedules
                WHERE schedule_id IN ({placeholders}) AND nurse_id IN (%s, %s)
            """
            params = tuple(all_swap_ids) + (requester_nurse_id, target_nurse_id)
            cur.execute(query, params)
            result = cur.fetchall()
            swapped_schedule_ids = [str(row[0]) for row in result]

    cur.close()
    conn.close()
    return render_template('admin/generate_schedule.html', schedule=schedule, swapped_schedule_ids=swapped_schedule_ids)



@admin_bp.route('/respond_swap', methods=['POST'])
def respond_swap():
    print("DEBUG: Received POST request to /respond_swap")
    print("DEBUG: request.form =", request.form)
    
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))
    
    request_id = request.form.get('request_id')
    swap_action = request.form.get('swap_action')  # Using the updated field name to avoid conflicts
    print("DEBUG: request_id =", request_id)
    print("DEBUG: swap_action =", swap_action)
    
    admin_id = session.get('user_id')
    print("DEBUG: admin_id =", admin_id)
    
    # Establish a database connection.
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Retrieve the swap request that is pending admin approval and belongs to the current admin.
    cur.execute("""
        SELECT request_id, requester_nurse_id, current_schedule_id, desired_schedule_id, target_nurse_id, status
        FROM shift_swap_requests
        WHERE request_id = %s AND status = 'NurseAccepted' AND admin_id = %s
    """, (request_id, admin_id))
    row = cur.fetchone()
    print("DEBUG: Fetched row from shift_swap_requests =", row)
    
    if not row:
        flash("Swap request not found or not pending admin approval.", "error")
        cur.close()
        conn.close()
        return redirect(url_for('admin.swap_requests'))
    
    req_id, requester_nurse_id, requester_schedule_id, desired_schedule_json, target_nurse_id, status = row
    print("DEBUG: Unpacked row =", req_id, requester_nurse_id, requester_schedule_id, desired_schedule_json, target_nurse_id, status)
    
    # Verify the admin is authorized for the target nurse.
    cur.execute("SELECT admin_id FROM nurses WHERE nurse_id = %s", (target_nurse_id,))
    admin_row = cur.fetchone()
    print("DEBUG: Fetched admin row from nurses table =", admin_row)
    if not admin_row or admin_row[0] != admin_id:
        flash("You are not authorized to approve this swap request.", "error")
        cur.close()
        conn.close()
        return redirect(url_for('admin.swap_requests'))
    
    if swap_action == 'approve':
        print("DEBUG: Approve action triggered")
        # Parse the desired schedule IDs from JSON.
        desired_schedule_ids = json.loads(desired_schedule_json)
        print("DEBUG: desired_schedule_ids =", desired_schedule_ids)
        
        # Retrieve target nurse's schedule IDs.
        cur.execute("SELECT schedule_id FROM schedules WHERE nurse_id = %s", (target_nurse_id,))
        target_schedule_rows = cur.fetchall()
        print("DEBUG: target_schedule_rows =", target_schedule_rows)
        target_schedule_ids = [r[0] for r in target_schedule_rows]
        print("DEBUG: target_schedule_ids =", target_schedule_ids)
        
        # Find the intersection.
        target_schedule_id = next((sid for sid in desired_schedule_ids if sid in target_schedule_ids), None)
        print("DEBUG: Computed target_schedule_id =", target_schedule_id)
        if not target_schedule_id:
            flash("Target nurse's schedule not found for swap.", "error")
            cur.close()
            conn.close()
            return redirect(url_for('admin.swap_requests'))
        
        # Execute the swap:
        # 1. Update the requester's schedule to be assigned to the target nurse.
        cur.execute("""
            UPDATE schedules
            SET nurse_id = %s
            WHERE schedule_id = %s
        """, (target_nurse_id, requester_schedule_id))
        print("DEBUG: Updated requester schedule to target nurse")
        
        # 2. Update the target nurse’s schedule to be assigned to the requester.
        cur.execute("""
            UPDATE schedules
            SET nurse_id = %s
            WHERE schedule_id = %s
        """, (requester_nurse_id, target_schedule_id))
        print("DEBUG: Updated target nurse schedule to requester")
        
        # 3. Mark the swap request as approved.
        cur.execute("""
            UPDATE shift_swap_requests
            SET status = 'AdminApproved'
            WHERE request_id = %s
        """, (request_id,))
        print("DEBUG: Marked swap request as AdminApproved")
        conn.commit()
        flash("Shift swap approved and executed successfully.", "success")
    
    elif swap_action == 'reject':
        print("DEBUG: Reject action triggered")
        cur.execute("""
            UPDATE shift_swap_requests
            SET status = 'AdminRejected'
            WHERE request_id = %s
        """, (request_id,))
        conn.commit()
        flash("Swap request rejected by admin.", "info")
    
    else:
        flash("Invalid action.", "error")
        print("DEBUG: Invalid swap_action received =", swap_action)
    
    # Update notification count in session so the notification dot reflects the current state.
    cur.execute("SELECT COUNT(*) FROM shift_swap_requests WHERE status = 'NurseAccepted' AND admin_id = %s", (admin_id,))
    session['notification_count'] = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    return redirect(url_for('admin.swap_requests'))



@admin_bp.route('/swap_requests', methods=['GET'])
def swap_requests():
    if 'user_id' not in session:
        flash('You need to log in first!', 'error')
        return redirect(url_for('auth.login'))
    
    admin_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    # Query swap requests that have been accepted by a nurse and await admin approval for the current admin.
    cur.execute("""
        SELECT request_id, requester_nurse_id, current_schedule_id, desired_schedule_id, target_nurse_id, status, notifications, created_at
        FROM shift_swap_requests
        WHERE (status = 'NurseAccepted' or status='AdminApproved' or status='AdminRejected') AND admin_id = %s
        ORDER BY created_at DESC
    """, (admin_id,))
    swap_requests_data = cur.fetchall()
    
    swap_requests = []
    # For each swap request, find the associated schedule id (session) that belongs to the target nurse.
    for row in swap_requests_data:
        # row[3] is a JSON string of desired schedule ids.
        desired_schedule_ids = json.loads(row[3])
        associated_schedule_id = None
        # Iterate over the list of schedule ids.
        for sched_id in desired_schedule_ids:
            # For each schedule, check if its nurse_id matches the target nurse id.
            cur.execute("SELECT nurse_id FROM schedules WHERE schedule_id = %s", (sched_id,))
            schedule = cur.fetchone()
            if schedule and schedule[0] == row[4]:
                associated_schedule_id = sched_id
                break
        # Prepare the display string: if an associated schedule was found, append it in parentheses.
        if associated_schedule_id:
            target_nurse_display = f"{row[4]} ({associated_schedule_id})"
        else:
            target_nurse_display = str(row[4])
        
        swap_requests.append({
            'request_id': row[0],
            'requester_nurse_id': row[1],
            'current_schedule_id': row[2],
            'desired_schedule_id': row[3],
            'target_nurse_id': target_nurse_display,  # updated display value
            'status': row[5],
            'notifications': row[6],
            'created_at': row[7]
        })
    
    cur.close()
    conn.close()
    
    return render_template('admin/notifications.html', swap_requests=swap_requests)



@admin_bp.route('/notification_count')
def notification_count():
    if 'user_id' not in session:
        return jsonify({'notification_count': 0})
    admin_id = session.get('user_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shift_swap_requests WHERE status = 'NurseAccepted' AND admin_id = %s", (admin_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return jsonify({'notification_count': count})





