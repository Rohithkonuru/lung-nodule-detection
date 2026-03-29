# Component Showcase

Complete guide to all reusable UI components in the LungAI Frontend.

---

## Table of Contents

1. [Button](#button)
2. [Input](#input)
3. [Card](#card)
4. [Badge](#badge)
5. [Alert](#alert)
6. [Spinner](#spinner)
7. [ProgressBar](#progressbar)
8. [Modal](#modal)
9. [LoadingSkeleton](#loadingskeleton)

---

## Button

Versatile button component with multiple variants and sizes.

### Usage

```jsx
import { Button } from '../components/common/UI';

// Primary button
<Button variant="primary" size="md">
  Click me
</Button>

// Secondary button
<Button variant="secondary" size="lg">
  Secondary Action
</Button>

// Danger button
<Button variant="danger" onClick={handleDelete}>
  Delete
</Button>

// Success button
<Button variant="success" size="sm">
  Confirm
</Button>

// Disabled state
<Button variant="primary" disabled>
  Processing...
</Button>
```

### Props

```typescript
interface ButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'danger' | 'success'; // default: 'primary'
  size?: 'sm' | 'md' | 'lg';                                 // default: 'md'
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
  [key: string]: any;
}
```

### CSS Classes

```
.btn-primary    - Blue button
.btn-secondary  - Gray outline button
.btn-danger     - Red button
```

---

## Input

Text input field with label and error support.

### Usage

```jsx
import { Input } from '../components/common/UI';
import { useState } from 'react';

function MyForm() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');

  return (
    <Input
      label="Email Address"
      type="email"
      placeholder="you@example.com"
      value={email}
      onChange={(e) => setEmail(e.target.value)}
      error={error}
    />
  );
}
```

### Props

```typescript
interface InputProps {
  label?: string;
  type?: string;                        // default: 'text'
  placeholder?: string;
  value?: string;
  onChange?: (e: ChangeEvent) => void;
  error?: string;
  className?: string;
  required?: boolean;
  disabled?: boolean;
  [key: string]: any;
}
```

### Features

- ✓ Label support
- ✓ Error message display
- ✓ Automatic focus styling
- ✓ Red border on error state

---

## Card

Flexible container component for content grouping.

### Usage

```jsx
import { Card } from '../components/common/UI';

// Simple card
<Card>
  <h2>Card Title</h2>
  <p>Card content goes here</p>
</Card>

// Hoverable card
<Card hover>
  <div>Click anywhere on this card</div>
</Card>

// Custom styling
<Card className="bg-blue-50 border-blue-200">
  <p>Custom styled card</p>
</Card>
```

### Props

```typescript
interface CardProps {
  children: ReactNode;
  hover?: boolean;      // Enable hover effect
  className?: string;
}
```

### Default Styling

- White background
- Soft shadow
- 16px border radius
- 24px padding
- Gray border

---

## Badge

Small label component for highlighting status.

### Usage

```jsx
import { Badge } from '../components/common/UI';

// Success badge
<Badge variant="success">Active</Badge>

// Danger badge (high risk)
<Badge variant="danger">High Risk</Badge>

// Warning badge
<Badge variant="warning">Pending</Badge>

// Gray badge
<Badge variant="gray">Inactive</Badge>

// Different sizes
<Badge size="lg">Large Badge</Badge>
<Badge size="md">Medium Badge</Badge>
<Badge size="sm">Small Badge</Badge>
```

### Props

```typescript
interface BadgeProps {
  children: ReactNode;
  variant?: 'primary' | 'success' | 'danger' | 'warning' | 'gray';  // default: 'primary'
  size?: 'sm' | 'md' | 'lg';                                        // default: 'sm'
}
```

---

## Alert

Alert/notification message component.

### Usage

```jsx
import { Alert } from '../components/common/UI';

// Success alert
<Alert
  type="success"
  title="Success!"
  message="Your scan has been uploaded successfully."
/>

// Error alert
<Alert
  type="error"
  title="Error"
  message="Failed to upload file. Please try again."
/>

// Warning alert
<Alert
  type="warning"
  title="Warning"
  message="High-risk nodules detected. Review carefully."
/>

// Info alert
<Alert
  type="info"
  title="Note"
  message="Processing may take several minutes."
/>

// Without title
<Alert type="success" message="Operation completed" />
```

### Props

```typescript
interface AlertProps {
  type?: 'success' | 'error' | 'warning' | 'info';  // default: 'info'
  title?: string;
  message: string;
  className?: string;
}
```

---

## Spinner

Loading spinner component.

### Usage

```jsx
import { Spinner } from '../components/common/UI';

// In a button
<Button disabled>
  <span className="flex items-center gap-2">
    <Spinner size="sm" />
    Loading...
  </span>
</Button>

// Standalone
<Spinner size="lg" />

// Custom styling
<div className="flex justify-center py-8">
  <Spinner size="md" className="text-primary" />
</div>
```

### Props

```typescript
interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';    // default: 'md'
  className?: string;
}
```

### Sizes

- `sm` - 16px (w-4 h-4)
- `md` - 32px (w-8 h-8) - default
- `lg` - 48px (w-12 h-12)

---

## ProgressBar

Visual progress indicator.

### Usage

```jsx
import { ProgressBar } from '../components/common/UI';

// 50% progress
<ProgressBar progress={50} />

// Custom styling
<div className="mb-4">
  <div className="flex justify-between text-sm mb-2">
    <span>Upload Progress</span>
    <span>{progress}%</span>
  </div>
  <ProgressBar progress={progress} className="h-3" />
</div>

// Animated progress
<ProgressBar progress={75} className="h-2 rounded-full" />
```

### Props

```typescript
interface ProgressBarProps {
  progress: number;      // 0-100
  className?: string;
}
```

### Features

- ✓ Smooth animation
- ✓ Blue color (primary)
- ✓ Responsive width
- ✓ Custom styling support

---

## Modal

Dialog/modal overlay component.

### Usage

```jsx
import { Modal, Button } from '../components/common/UI';
import { useState } from 'react';

function MyComponent() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setIsOpen(true)}>
        Open Modal
      </Button>

      <Modal
        isOpen={isOpen}
        title="Confirm Action"
        onClose={() => setIsOpen(false)}
        footer={
          <div className="flex gap-3 justify-end">
            <Button
              variant="secondary"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="danger">Delete</Button>
          </div>
        }
      >
        <p>Are you sure you want to delete this scan?</p>
      </Modal>
    </>
  );
}
```

### Props

```typescript
interface ModalProps {
  isOpen: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}
```

### Features

- ✓ Dark overlay backdrop
- ✓ Close button (✕)
- ✓ Optional footer section
- ✓ Centered, max-width container
- ✓ Click outside to close overlay

---

## LoadingSkeleton

Skeleton loading placeholder.

### Usage

```jsx
import { LoadingSkeleton } from '../components/common/UI';

// Simple skeleton
<LoadingSkeleton className="h-4 w-full mb-4" />

// Multiple skeletons
<div className="space-y-4">
  <LoadingSkeleton className="h-8 w-3/4" />
  <LoadingSkeleton className="h-4 w-full" />
  <LoadingSkeleton className="h-4 w-5/6" />
</div>

// Avatar skeleton
<LoadingSkeleton className="w-12 h-12 rounded-full" />

// Table row skeleton
<div className="grid grid-cols-4 gap-4">
  <LoadingSkeleton className="h-6" />
  <LoadingSkeleton className="h-6" />
  <LoadingSkeleton className="h-6" />
  <LoadingSkeleton className="h-6" />
</div>
```

### Props

```typescript
interface LoadingSkeletonProps {
  className?: string;
}
```

### Default Styling

- Gray gradient animation
- 8px border radius
- Smooth pulsing effect

---

## Layout Components

### MainLayout

Main application layout with sidebar.

```jsx
import { MainLayout } from '../components/layout/MainLayout';

function Page() {
  return (
    <MainLayout>
      <h1>Page Title</h1>
      <p>Page content here</p>
    </MainLayout>
  );
}
```

### Sidebar Navigation

Automatically includes:
- LungAI logo
- Navigation links (Dashboard, Upload, Results, Reports, History)
- Logout button
- Mobile hamburger menu

---

## Styling Tips

### Using Tailwind Classes

All components support `className` prop for additional Tailwind classes:

```jsx
<Button className="w-full shadow-lg">
  Full Width Button
</Button>

<Card className="bg-blue-50 border-blue-300">
  Custom Card
</Card>
```

### Common Utilities

```jsx
// Spacing
className="mt-4 mb-8 px-6 py-4"

// Display
className="flex items-center gap-2"

// Sizing
className="w-full h-12"

// Colors
className="text-primary bg-light"

// Responsive
className="grid grid-cols-1 md:grid-cols-2 gap-4"
```

---

## Color Reference

```javascript
// Tailwind colors defined in tailwind.config.js
primary:   #2563EB   (Blue)
secondary: #1E40AF   (Dark Blue)
success:   #10B981   (Green)
danger:    #EF4444   (Red)
warning:   #F59E0B   (Orange)
light:     #F3F4F6   (Light Gray)
dark:      #111827   (Dark Gray)
```

---

## Examples

### Login Form

```jsx
import { Card, Button, Input, Alert } from '../components/common/UI';

export function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Handle login
  };

  return (
    <Card className="max-w-md mx-auto">
      {error && <Alert type="error" message={error} className="mb-4" />}
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        
        <Button type="submit" variant="primary" size="lg" className="w-full">
          Sign In
        </Button>
      </form>
    </Card>
  );
}
```

### Status Table

```jsx
import { Card, Badge } from '../components/common/UI';

export function StatusTable({ items }) {
  return (
    <Card>
      <table className="w-full">
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b">
              <td className="py-3">{item.name}</td>
              <td className="py-3">
                <Badge variant={item.status === 'active' ? 'success' : 'gray'}>
                  {item.status}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
```

---

## Best Practices

1. ✅ Always import from `src/components/common/UI`
2. ✅ Use semantic HTML for accessibility
3. ✅ Combine components for complex layouts
4. ✅ Use Tailwind for custom styling
5. ✅ Keep components focused and reusable
6. ✅ Use TypeScript for prop validation
7. ✅ Test components in different states

---

**Last Updated:** 2024
**Version:** 1.0.0
