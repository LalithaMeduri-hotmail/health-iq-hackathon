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

// Mirrors `_TRIVIAL_PINS` in backend/app/models/account.py. Without this the backend rejects the
// PIN with a raw 422 that names no field, so the user is told "something went wrong" and has no
// way to guess that their PIN is the problem.
const TRIVIAL_PINS = new Set([
  '0000', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999',
  '1234', '4321', '0123', '1000', '2000',
]);

const registerSchema = z
  .object({
    username: z
      .string()
      .trim()
      .regex(/^[a-zA-Z0-9_.]{3,32}$/, 'Use 3-32 letters, digits, "." or "_".'),
    mobile: z.string().trim().regex(/^\+?[0-9]{7,15}$/, 'Enter a valid mobile number.').or(z.literal('')),
    email: z.string().trim().email('Enter a valid email address.').or(z.literal('')),
    pin: z
      .string()
      .regex(/^\d{4}$/, 'Enter a 4-digit PIN.')
      .refine((pin) => !TRIVIAL_PINS.has(pin), 'Choose a less predictable PIN.'),
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
  if (!(error instanceof ApiError)) {
    return 'Something went wrong creating your account. Please try again.';
  }

  const { status, detail } = error.problem;

  if (status === 409) {
    return 'That username, mobile, or email is already registered.';
  }

  // FastAPI's own request-validation failure is not an RFC 7807 problem: it has no `status` and
  // `detail` is an array of field errors, so it has to be flattened before it can be displayed.
  if (Array.isArray(detail)) {
    const messages = (detail as Array<{ msg?: string }>)
      .map((item) => item.msg?.replace(/^Value error,\s*/, ''))
      .filter(Boolean);
    return messages.length > 0
      ? messages.join(' ')
      : 'Please check the details you entered.';
  }

  if (typeof detail === 'string' && (status === 400 || status === 422)) {
    return detail;
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
          <Input
            label="Username"
            hideLabel
            placeholder="Username"
            autoComplete="username"
            error={errors.username?.message}
            {...register('username')}
          />
          <Input
            label="Mobile number"
            hideLabel
            placeholder="Mobile number"
            autoComplete="tel"
            error={errors.mobile?.message}
            {...register('mobile')}
          />
          <Input
            label="Email"
            hideLabel
            placeholder="Email"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register('email')}
          />
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
