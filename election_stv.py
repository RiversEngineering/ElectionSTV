import streamlit as st
import pandas as pd
import plotly.express as px
import time
import numpy as np

def run_app():
    st.set_page_config(layout="wide")
    st.title("Ranked Choice Election Runner (Meek's Method)")

    if 'step_delay' not in st.session_state:
        st.session_state.step_delay = 0.5
    if 'election_started' not in st.session_state:
        st.session_state.election_started = False
    if 'seats' not in st.session_state:
        st.session_state.seats = 2

    # File Selection Interface
    with st.expander("File Import", expanded=not st.session_state.election_started):
        col1, col2 = st.columns(2)
        # Using keys to preserve state across reruns
        votes_file = col1.file_uploader("Upload Ranked Choice CSV", type=['csv'], key="votes_uploader")
        gender_file = col2.file_uploader("Upload Candidate Gender CSV", type=['csv'], key="gender_uploader")

    if votes_file and gender_file:
        votes_df = pd.read_csv(votes_file)
        gender_df = pd.read_csv(gender_file)
        
        gender_map = dict(zip(gender_df.iloc[:, 0], gender_df.iloc[:, 1]))
        all_candidates = list(gender_map.keys())
        
        ballots = votes_df.iloc[:, 1:].values.tolist()
        ballots = [[str(c).strip() for c in b if pd.notna(c) and str(c).strip() != ''] for b in ballots]

        if not st.session_state.election_started:
            c1, c2 = st.columns(2)
            if c1.button("2 Seat Election"):
                st.session_state.seats = 2
                st.session_state.election_started = True
                st.rerun()
            if c2.button("3 Seat Election"):
                st.session_state.seats = 3
                st.session_state.election_started = True
                st.rerun()
        
        if st.session_state.election_started:
            run_col1, run_col2, run_col3 = st.columns(3)
            start_run = run_col1.button("Run")
            start_slow = run_col2.button("Run Slow")
            if run_col3.button("Restart"):
                st.session_state.election_started = False
                st.rerun()

            if start_run or start_slow:
                st.session_state.step_delay = 0.5 if start_run else 2.0
                
                num_seats = st.session_state.seats
                total_ballots = len(ballots)
                quota = np.floor(total_ballots / (num_seats + 1)) + 1
                
                keep_values = {cand: 1.0 for cand in all_candidates}
                status = {cand: "Active" for cand in all_candidates}
                
                chart_placeholder = st.empty()

                def update_viz(tallies, current_status, step_name, final=False):
                    df_viz = pd.DataFrame({
                        'Candidate': list(tallies.keys()),
                        'Votes': list(tallies.values()),
                        'Status': [current_status[c] for c in tallies.keys()]
                    })
                    
                    # Highlight logic: Final winners get a distinct "Winner" status for the color map
                    if final:
                        df_viz['Status'] = df_viz.apply(lambda x: "Winner" if x['Status'] == "Elected" else x['Status'], axis=1)

                    fig = px.bar(df_viz, x='Votes', y='Candidate', orientation='h',
                                 color='Status', 
                                 title=f"Step: {step_name}",
                                 color_discrete_map={
                                     "Active": "#636EFA", 
                                     "Elected": "#00CC96", 
                                     "Eliminated": "#EF553B",
                                     "Winner": "#FFD700" # Gold for final winners
                                 })
                    fig.add_vline(x=quota, line_dash="dash", line_color="red", annotation_text=f"Quota: {quota}")
                    chart_placeholder.plotly_chart(fig, use_container_width=True)
                    time.sleep(st.session_state.step_delay)

                # Initial Tally
                initial_tallies = {cand: 0.0 for cand in all_candidates}
                for b in ballots:
                    if b: initial_tallies[b[0]] += 1.0
                update_viz(initial_tallies, status, "Initial Tally")

                # Gender Rule Case 2
                initial_elected = [c for c, v in initial_tallies.items() if v >= quota]
                if len(initial_elected) >= num_seats:
                    winners_slice = initial_elected[:num_seats]
                    genders_represented = set(gender_map[c] for c in winners_slice)
                    if len(genders_represented) < 2:
                        weakest = min(winners_slice, key=lambda x: initial_tallies[x])
                        status[weakest] = "Eliminated"
                        keep_values[weakest] = 0.0
                        update_viz(initial_tallies, status, f"Gender Rule: Removed {weakest} (Diversity Requirement)")

                # Election Loop
                election_complete = False
                while not election_complete:
                    for _ in range(10): 
                        current_tallies = {cand: 0.0 for cand in all_candidates}
                        for ballot in ballots:
                            weight = 1.0
                            for cand in ballot:
                                if status[cand] != "Eliminated":
                                    contribution = weight * keep_values[cand]
                                    current_tallies[cand] += contribution
                                    weight -= contribution
                                    if weight <= 0: break
                        
                        for cand in all_candidates:
                            if status[cand] == "Elected":
                                # Avoid division by zero
                                t_val = max(current_tallies[cand], 0.0001)
                                keep_values[cand] = (keep_values[cand] * quota) / t_val
                            elif status[cand] == "Eliminated":
                                keep_values[cand] = 0.0
                    
                    for cand in all_candidates:
                        if status[cand] == "Active" and current_tallies[cand] >= quota:
                            status[cand] = "Elected"
                    
                    update_viz(current_tallies, status, "Applying Meek's Distribution")

                    winners = [c for c, s in status.items() if s == "Elected"]
                    active_cands = [c for c, s in status.items() if s == "Active"]
                    
                    # Gender Rule Case 1
                    if len(winners) == num_seats - 1 and len(active_cands) > 0:
                        genders_in_winners = set(gender_map[c] for c in winners)
                        if len(genders_in_winners) == 1:
                            sole_gender = list(genders_in_winners)[0]
                            for c in all_candidates:
                                if gender_map[c] == sole_gender:
                                    status[c] = "Eliminated"
                                    keep_values[c] = 0.0
                                else:
                                    status[c] = "Active"
                                    keep_values[c] = 1.0
                            update_viz(current_tallies, status, "Gender Rule: Rebalancing for Diversity")
                            continue 

                    if len(winners) >= num_seats or not active_cands:
                        election_complete = True
                        update_viz(current_tallies, status, "Election Complete - Winners Highlighted", final=True)
                        st.success(f"Election Concluded. Winners: {', '.join(winners)}")
                        break

                    if not any(current_tallies[c] >= quota for c in active_cands):
                        weakest = min(active_cands, key=lambda x: current_tallies[x])
                        status[weakest] = "Eliminated"
                        keep_values[weakest] = 0.0
                        update_viz(current_tallies, status, f"Eliminating {weakest}")

if __name__ == "__main__":
    run_app()
