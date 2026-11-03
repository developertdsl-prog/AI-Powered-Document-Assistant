export interface UserRecord {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  full_name?: string;
}
