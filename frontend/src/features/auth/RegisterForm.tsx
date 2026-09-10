/** Registration form: username + optional mobile/email + PIN (account module). */

import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { Button, Card, Input, PinInput } from '@/components/ui';
import { ApiError } from '@/lib/apiClient';

import { useAuth } from './AuthContext';
import styles from './auth.module.css';

const registerSchema = z
  .object({
    username: z
      .string()
      .trim()
      .regex(/^[a-zA-Z0-9_.]{3,32}$/, 'Use 3-32 letters, digits, "." or "_".'),
    mobile: z.string().trim().regex(/^\+?[0-9]{7,15}$/, 'Enter a valid mobile number.').or(z.literal('')),
    email: z.string().trim().email('Enter a valid email address.').or(z.literal('')),
    pin: z.string().regex(/^\d{4}$/, 'Enter a 4-digit PIN.'),
    confirmPin: z.string(),
  })
  .refine((values) => Boolean(values.mobile) || Boolean(values.email), {
    message: 'Add a mobile number or email so you can recover your account.',
    path: ['email'],
  })
  .refine((values) => values.pin === values.confirmPin, {
    message: 'PINs do not match.',
    path: ['confirmPin'],
  });

type RegisterForm = z.infer<typeof registerSchema>;

function registerErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.problem.status === 409) {
      return 'That username, mobile, or email is already registered.';
    }
    if (error.problem.status === 400 || error.problem.status === 422) {
      return error.problem.detail || 'Please check the details you entered.';
    }
  }
  return 'Something went wrong creating your account. Please try again.';
}

export function RegisterForm() {
  const navigate = useNavigate();
  const { register: createAccount } = useAuth();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { username: '', mobile: '', email: '', pin: '', confirmPin: '' },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await createAccount({
        username: values.username,
        mobile: values.mobile || undefined,
        email: values.email || undefined,
        pin: values.pin,
      });
      navigate('/', { replace: true });
    } catch (error) {
      setFormError(registerErrorMessage(error));
    }
  });

  return (
    <div className={styles.page}>
      <Card className={styles.card} title="Create your account" subtitle="A mobile number or email lets you recover access later.">
        <form className={styles.form} onSubmit={onSubmit} noValidate>
          <Input label="Username" autoComplete="username" error={errors.username?.message} {...register('username')} />
          <Input label="Mobile number" autoComplete="tel" error={errors.mobile?.message} {...register('mobile')} />
          <Input label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
          <Controller
            name="pin"
            control={control}
            render={({ field }) => (
              <PinInput label="PIN" value={field.value} onChange={field.onChange} error={errors.pin?.message} />
            )}
          />
          <Controller
            name="confirmPin"
            control={control}
            render={({ field }) => (
              <PinInput
                label="Confirm PIN"
                value={field.value}
                onChange={field.onChange}
                error={errors.confirmPin?.message}
              />
            )}
          />
          <p className={styles.hintText}>Choose a 4-digit PIN. Avoid obvious patterns like 1234 or 0000.</p>
          {formError && <p className={styles.formError}>{formError}</p>}
          <div className={styles.actions}>
            <Button type="submit" size="lg" isLoading={isSubmitting}>
              Create account
            </Button>
          </div>
        </form>
        <p className={styles.switchLine}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </Card>
    </div>
  );
}
