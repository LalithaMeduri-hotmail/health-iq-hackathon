/** Login form: username, mobile, or email + PIN (account module). */

import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { Button, Card, Input, PinInput } from '@/components/ui';
import { ApiError } from '@/lib/apiClient';

import { useAuth } from './AuthContext';
import styles from './auth.module.css';

const loginSchema = z.object({
  identifier: z.string().trim().min(3, 'Enter your username, mobile, or email.'),
  pin: z.string().regex(/^\d{4}$/, 'Enter your 4-digit PIN.'),
});

type LoginForm = z.infer<typeof loginSchema>;

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.problem.status === 429) {
      return 'Too many failed attempts. This account is temporarily locked - try again later.';
    }
    if (error.problem.status === 401) {
      return 'Invalid username/mobile/email or PIN.';
    }
  }
  return 'Something went wrong signing you in. Please try again.';
}

export function LoginForm() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);
  const wasSessionExpired = searchParams.get('reason') === 'expired';

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema), defaultValues: { identifier: '', pin: '' } });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login(values);
      navigate('/', { replace: true });
    } catch (error) {
      setFormError(loginErrorMessage(error));
    }
  });

  return (
    <div className={styles.page}>
      <Card className={styles.card} title="Sign in" subtitle="Use your username, mobile number, or email with your PIN.">
        <form className={styles.form} onSubmit={onSubmit} noValidate>
          {wasSessionExpired && !formError && (
            <p className={styles.sessionNotice} role="status">
              Your session has expired. Please sign in again to pick up where you left off.
            </p>
          )}
          <Input
            label="Username, mobile, or email"
            hideLabel
            placeholder="Username, mobile, or email"
            autoComplete="username"
            error={errors.identifier?.message}
            {...register('identifier')}
          />
          <Controller
            name="pin"
            control={control}
            render={({ field }) => (
              <PinInput label="PIN" value={field.value} onChange={field.onChange} error={errors.pin?.message} />
            )}
          />
          {formError && <p className={styles.formError}>{formError}</p>}
          <div className={styles.actions}>
            <Button type="submit" size="lg" isLoading={isSubmitting}>
              Sign in
            </Button>
          </div>
        </form>
        <p className={styles.switchLine}>
          New to HealthIQ? <Link to="/register">Create an account</Link>
        </p>
      </Card>
    </div>
  );
}
