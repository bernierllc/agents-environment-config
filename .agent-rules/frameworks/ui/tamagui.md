# Tamagui Development Rules

## Component Library Philosophy

- **ALWAYS prefer vanilla Tamagui components** when creating/updating UI
- **ALWAYS prefer Bento components** for complex UI patterns
- **TREAT packages/ui as a cross-platform, portable package**
- **MAKE components reusable, well-documented, and refactored**

## Tamagui Component Usage

- Use Tamagui primitives (`Button`, `Text`, `View`, `Stack`, `XStack`, `YStack`, etc.)
- Prefer Tamagui styling over custom CSS/styling
- Use Tamagui themes and design tokens
- Leverage Tamagui's responsive design capabilities

## Property Mappings

### Core Style Properties
- `borderColor` → `bc`
- `backgroundColor` → `bg` (use `$color1` to `$color12` or `$blue1` to `$blue12`)
- `borderRadius` → `rounded` (use `$1` to `$12` for consistent spacing)
- `alignItems` → `items`
- `justifyContent` → `justify`

### Spacing Properties
- `paddingHorizontal` → `px`
- `paddingVertical` → `py`
- `padding` → `p`
- `marginHorizontal` → `mx`
- `marginVertical` → `my`
- `margin` → `m`

### Size Properties
- `width` → `w`
- `height` → `h`
- `minWidth` → `minW`
- `maxWidth` → `maxW`

### Typography Properties
- `fontSize` → `fos`
- `fontWeight` → `fow`
- `color` → `col`
- `textAlign` → `text`

### Shadow Properties
- **DO NOT use** `shadowColor`, `shadowOffset`, `shadowOpacity`, `shadowRadius`
- **USE** `boxShadow` property instead

## Color Variables

- **Theme colors**: `$color1` to `$color12`
- **Semantic colors**: `$blue1` to `$blue12`, `$green1` to `$green12`, etc.
- **Surface colors**: `$background`, `$backgroundHover`, `$backgroundPress`
- **Text colors**: `$color`, `$colorHover`, `$colorPress`

## Examples

### ❌ Avoid - Standard React Native Properties
```tsx
<View
  backgroundColor="#3B82F6"
  borderColor="#1E40AF"
  borderRadius={12}
  paddingHorizontal={16}
  shadowColor="#000"
  shadowOffset={{ width: 0, height: 2 }}
/>
```

### ✅ Prefer - Tamagui Shorthand Properties
```tsx
<View
  bg="$blue9"
  bc="$blue10"
  rounded="$3"
  px="$4"
  py="$2"
  boxShadow="0 2px 8px rgba(0,0,0,0.1)"
/>
```

## Debugging

### Build-Time Debugging
- Add `// debug` to the top of any file for build-time analysis
- Add `// debug-verbose` for even more detailed information

### Runtime Debugging
- Add `debug` prop to Tamagui components for runtime information
- Use `debug="break"` to break at the beginning of rendering
- Use `debug="verbose"` for more detailed debug information

```tsx
<Button debug>Hello world</Button>
<Button debug="break">Debug me</Button>
<Button debug="verbose">Detailed info</Button>
```

### Environment Debugging
```bash
DEBUG=tamagui pnpm build
DEBUG=tamagui pnpm dev
```

## Component Development Standards

### Component Structure
```tsx
interface ComponentProps {
  prop1: string;
  prop2: number;
  optionalProp?: boolean;
}

export const ComponentName = ({ prop1, prop2, optionalProp }: ComponentProps) => {
  return (
    <TamaguiComponent>
      {/* Content */}
    </TamaguiComponent>
  )
}
```

### Best Practices
1. Use theme variables instead of hardcoded colors
2. Use shorthand properties for cleaner code
3. Leverage spacing tokens (`$1` to `$12`) for consistency
4. Use `boxShadow` instead of individual shadow properties
5. Prefer semantic color names (`$blue9`, `$green6`) over generic ones

## Cross-Platform Considerations

- Use platform-specific files when needed (`.native.tsx`, `.web.tsx`)
- Test on all platforms (web, iOS, Android)
- Use responsive design patterns
- Consider accessibility across platforms

## References
- **React Native**: See `stacks/react-native/expo-development.mdc`
- **TypeScript**: See `languages/typescript/typing-standards.mdc`
- **Testing**: See `frameworks/testing/standards.mdc`
