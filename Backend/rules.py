from datetime import timedelta

def get_reference_date(current_df):
    return current_df["exposure_date"].max()

def calculate_password_reset_candidates(current_df, master_df):
    if current_df.empty or master_df.empty:
        return current_df
        
    six_months_ago = get_reference_date(current_df) - timedelta(days=183)
    
    # Filter directly to get only the relevant emails
    recent_exposed_emails = master_df.loc[
        master_df["last_exposed_date"] >= six_months_ago, "email"
    ]

    # Efficient negative look-up using boolean indexing
    return current_df[~current_df["email"].isin(recent_exposed_emails)]

def get_password_reset_count(current_df, master_df):
    return len(calculate_password_reset_candidates(current_df, master_df))

def get_recently_exposed_users(current_df, master_df):
    if master_df.empty or current_df.empty:
        return master_df
        
    six_months_ago = get_reference_date(current_df) - timedelta(days=183)
    return master_df[master_df["last_exposed_date"] >= six_months_ago]

def get_exposure_breakdown_by_source(recent_df):
    return recent_df.groupby("source").size().to_dict()